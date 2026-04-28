from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_UNIVERSE, ExperimentMeta, load_market_panel, record_experiment, save_csv


def _build_scores(market, lookback: int) -> pd.DataFrame:
    close = market.close
    returns = close.pct_change()
    sharpe = returns.rolling(lookback, min_periods=max(5, lookback // 2)).mean() / returns.rolling(
        lookback, min_periods=max(5, lookback // 2)
    ).std(ddof=0)
    adv = market.amount.rolling(lookback, min_periods=max(5, lookback // 2)).mean()
    cap_proxy = market.close.rolling(lookback, min_periods=max(5, lookback // 2)).mean() * market.volume.rolling(
        lookback, min_periods=max(5, lookback // 2)
    ).mean()
    spread_proxy = returns.abs().rolling(lookback, min_periods=max(5, lookback // 2)).mean()
    rows: list[dict[str, object]] = []
    for date in close.index[lookback:]:
        rows.append(
            {
                "date": date,
                "sharpe": sharpe.loc[date],
                "adv": adv.loc[date],
                "cap_proxy": cap_proxy.loc[date],
                "spread_proxy": spread_proxy.loc[date],
            }
        )
    return pd.DataFrame(rows)


def _select_history(market, lookback: int, top_n: int, adv_q: float, spread_q: float, cap_q: float) -> pd.DataFrame:
    scores = _build_scores(market, lookback)
    rows: list[dict[str, object]] = []
    for _, row in scores.iterrows():
        date = pd.Timestamp(row["date"])
        sharpe_row = row["sharpe"].dropna().sort_values(ascending=False)
        if sharpe_row.empty:
            continue
        adv_row = row["adv"].reindex(sharpe_row.index)
        cap_row = row["cap_proxy"].reindex(sharpe_row.index)
        spread_row = row["spread_proxy"].reindex(sharpe_row.index)
        adv_cutoff = float(adv_row.quantile(adv_q))
        spread_cutoff = float(spread_row.quantile(spread_q))
        cap_cutoff = float(cap_row.quantile(cap_q))
        filtered = sharpe_row[
            (adv_row >= adv_cutoff)
            & (spread_row <= spread_cutoff)
            & (cap_row >= cap_cutoff)
        ]
        chosen = filtered.head(top_n)
        if chosen.empty:
            chosen = sharpe_row.head(top_n)
        for rank, (symbol, score) in enumerate(chosen.items(), start=1):
            rows.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "symbol": symbol,
                    "rank": rank,
                    "score": float(score),
                    "adv": float(adv_row.get(symbol, np.nan)),
                    "cap_proxy": float(cap_row.get(symbol, np.nan)),
                    "spread_proxy": float(spread_row.get(symbol, np.nan)),
                }
            )
    return pd.DataFrame(rows)


def _stability_stats(selection: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for date, group in selection.groupby("date"):
        rows.append({"date": date, "selected": set(group["symbol"])})
    rows = sorted(rows, key=lambda item: item["date"])
    metrics: list[dict[str, object]] = []
    prev: set[str] | None = None
    for item in rows:
        current = item["selected"]
        if prev is None:
            overlap = np.nan
            turnover = np.nan
        else:
            union = prev | current
            overlap = len(prev & current) / len(union) if union else np.nan
            turnover = 1.0 - overlap if np.isfinite(overlap) else np.nan
        metrics.append(
            {
                "date": item["date"],
                "selected_count": len(current),
                "overlap_rate": overlap,
                "turnover_rate": turnover,
            }
        )
        prev = current
    return pd.DataFrame(metrics)


def main() -> None:
    meta = ExperimentMeta(
        code="48",
        title="Sharpe驱动选股敏感性",
        goal="验证不同滚动窗口和流动性门槛下的 Sharpe 排序稳定性。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20230102", "20240315")
    scenarios = [
        {"lookback": 20, "adv_q": 0.40, "spread_q": 0.60, "cap_q": 0.40, "label": "short_loose"},
        {"lookback": 60, "adv_q": 0.60, "spread_q": 0.40, "cap_q": 0.60, "label": "mid_balanced"},
        {"lookback": 120, "adv_q": 0.75, "spread_q": 0.25, "cap_q": 0.75, "label": "long_strict"},
    ]

    selection_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []
    stability_frames: list[pd.DataFrame] = []
    for scenario in scenarios:
        selected = _select_history(
            market,
            lookback=scenario["lookback"],
            top_n=3,
            adv_q=scenario["adv_q"],
            spread_q=scenario["spread_q"],
            cap_q=scenario["cap_q"],
        )
        selected["scenario"] = scenario["label"]
        selection_frames.append(selected)
        stability = _stability_stats(selected)
        stability["scenario"] = scenario["label"]
        stability_frames.append(stability)
        summary_rows.append(
            {
                "scenario": scenario["label"],
                "lookback": scenario["lookback"],
                "selected_rows": len(selected),
                "unique_symbols": selected["symbol"].nunique() if not selected.empty else 0,
                "avg_selected_count": float(stability["selected_count"].mean()) if not stability.empty else np.nan,
                "avg_overlap_rate": float(stability["overlap_rate"].dropna().mean()) if not stability.empty else np.nan,
                "avg_turnover_rate": float(stability["turnover_rate"].dropna().mean()) if not stability.empty else np.nan,
            }
        )

    selection = pd.concat(selection_frames, ignore_index=True) if selection_frames else pd.DataFrame()
    stability = pd.concat(stability_frames, ignore_index=True) if stability_frames else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)

    artifact_dir = ROOT / "artifacts"
    save_csv(selection, artifact_dir / "selection_history.csv")
    save_csv(stability, artifact_dir / "stability_metrics.csv")
    save_csv(summary, artifact_dir / "scenario_summary.csv")

    varied_windows = summary["lookback"].nunique() if not summary.empty else 0
    stable_change = bool((summary["avg_turnover_rate"].max() - summary["avg_turnover_rate"].min()) > 0.01) if len(summary) > 1 else False
    steps = [
        "用 rolling Sharpe 对标的排序，并在每个日期做流动性、价差和市值代理过滤。",
        "分别测试 20/60/120 日窗口，观察候选集变化是否明显。",
        "统计连续日期的 overlap 和 turnover，检查信号稳定性。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = [
        "artifacts/selection_history.csv",
        "artifacts/stability_metrics.csv",
        "artifacts/scenario_summary.csv",
    ]
    if varied_windows >= 3 and stable_change:
        status = "pass"
        conclusion = "Sharpe 选股对窗口和流动性门槛敏感，信号稳定性可量化。"
    else:
        status = "fail"
        conclusion = "Sharpe 选股敏感性没有形成可区分的结果。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
