from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_UNIVERSE, ExperimentMeta, apply_costs, execute_rebalance, load_market_panel, record_experiment, save_csv


def _build_targets(market, lookback: int = 20, top_n: int = 3, weight_mode: str = "blend") -> pd.DataFrame:
    close = market.close
    returns = close.pct_change()
    sharpe = returns.rolling(lookback, min_periods=max(5, lookback // 2)).mean() / returns.rolling(
        lookback, min_periods=max(5, lookback // 2)
    ).std(ddof=0)
    inv_vol = 1.0 / returns.rolling(lookback, min_periods=max(5, lookback // 2)).std(ddof=0).replace(0.0, np.nan)
    adv = market.amount.rolling(lookback, min_periods=max(5, lookback // 2)).mean()
    cap_proxy = market.close.rolling(lookback, min_periods=max(5, lookback // 2)).mean() * market.volume.rolling(
        lookback, min_periods=max(5, lookback // 2)
    ).mean()
    spread_proxy = returns.abs().rolling(lookback, min_periods=max(5, lookback // 2)).mean()

    rows: list[dict[str, object]] = []
    for date in close.index[lookback:-1]:
        s_row = sharpe.loc[date].dropna().sort_values(ascending=False)
        if s_row.empty:
            continue
        adv_row = adv.loc[date].reindex(s_row.index)
        cap_row = cap_proxy.loc[date].reindex(s_row.index)
        spread_row = spread_proxy.loc[date].reindex(s_row.index)
        filtered = s_row[
            (adv_row >= adv_row.quantile(0.50))
            & (cap_row >= cap_row.quantile(0.50))
            & (spread_row <= spread_row.quantile(0.60))
        ]
        chosen = filtered.head(top_n)
        if chosen.empty:
            chosen = s_row.head(top_n)
        inv_row = inv_vol.loc[date].reindex(chosen.index).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        score_row = chosen.abs().fillna(0.0)
        if weight_mode == "equal":
            weights = pd.Series(1.0 / len(chosen), index=chosen.index)
        elif weight_mode == "sharpe":
            weights = score_row / score_row.sum() if score_row.sum() > 0 else pd.Series(1.0 / len(chosen), index=chosen.index)
        elif weight_mode == "inv_vol":
            weights = inv_row / inv_row.sum() if inv_row.sum() > 0 else pd.Series(1.0 / len(chosen), index=chosen.index)
        else:
            blend = 0.5 * (score_row / score_row.sum() if score_row.sum() > 0 else pd.Series(1.0 / len(chosen), index=chosen.index))
            blend += 0.5 * (inv_row / inv_row.sum() if inv_row.sum() > 0 else pd.Series(1.0 / len(chosen), index=chosen.index))
            weights = blend / blend.sum()

        for symbol, weight in weights.items():
            rows.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "symbol": symbol,
                    "weight": float(weight),
                    "score": float(chosen.get(symbol, np.nan)),
                    "volatility": float(1.0 / inv_row.get(symbol, np.nan))
                    if pd.notna(inv_row.get(symbol, np.nan)) and inv_row.get(symbol, 0.0) != 0.0
                    else np.nan,
                }
            )
    return pd.DataFrame(rows)


def _subsample_targets(targets: pd.DataFrame, step: int) -> pd.DataFrame:
    dates = sorted(pd.to_datetime(targets["date"]).unique())
    keep = {date.strftime("%Y-%m-%d") for idx, date in enumerate(dates) if idx % step == 0}
    return targets[targets["date"].isin(keep)].reset_index(drop=True)


def _scenario_run(targets: pd.DataFrame, market, max_adv_pct: float, fee_bps: float, slippage_bps: float) -> dict[str, object]:
    execution = execute_rebalance(targets, market, initial_cash=1_000_000.0, lot_size=100, max_adv_pct=max_adv_pct)
    costed = apply_costs(execution.pnl, fee_bps=fee_bps, slippage_bps=slippage_bps)
    final_equity = float(costed["net_equity"].iloc[-1]) if not costed.empty else np.nan
    turnover = float(execution.pnl["turnover"].sum()) if not execution.pnl.empty else np.nan
    cost = float(costed["cost"].sum()) if not costed.empty else np.nan
    avg_fill = float(execution.holdings["fill_ratio"].mean()) if not execution.holdings.empty else np.nan
    return {
        "final_equity": final_equity,
        "turnover": turnover,
        "cost": cost,
        "avg_fill_ratio": avg_fill,
        "execution": execution,
        "costed": costed,
    }


def main() -> None:
    meta = ExperimentMeta(
        code="49",
        title="组合优化对比",
        goal="比较权重组合、流动性约束、交易成本和再平衡频率对组合表现的影响。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20230102", "20240315")
    base_targets = _build_targets(market, lookback=20, top_n=3, weight_mode="blend")
    scheme_targets = {
        "sharpe_only": _build_targets(market, lookback=20, top_n=3, weight_mode="sharpe"),
        "inv_vol_only": _build_targets(market, lookback=20, top_n=3, weight_mode="inv_vol"),
        "blend_50_50": base_targets,
    }

    scheme_rows: list[dict[str, object]] = []
    for name, targets in scheme_targets.items():
        result = _scenario_run(targets, market, max_adv_pct=0.05, fee_bps=5, slippage_bps=1)
        scheme_rows.append(
            {
                "scheme": name,
                "rows": len(targets),
                "final_equity": result["final_equity"],
                "turnover": result["turnover"],
                "cost": result["cost"],
                "avg_fill_ratio": result["avg_fill_ratio"],
            }
        )

    liquidity_rows: list[dict[str, object]] = []
    for cap in [0.20, 0.05, 0.01]:
        result = _scenario_run(base_targets, market, max_adv_pct=cap, fee_bps=5, slippage_bps=1)
        liquidity_rows.append(
            {
                "max_adv_pct": cap,
                "final_equity": result["final_equity"],
                "turnover": result["turnover"],
                "cost": result["cost"],
                "avg_fill_ratio": result["avg_fill_ratio"],
            }
        )

    cost_rows: list[dict[str, object]] = []
    for bps in [2, 5, 10]:
        result = _scenario_run(base_targets, market, max_adv_pct=0.05, fee_bps=bps, slippage_bps=1)
        cost_rows.append(
            {
                "fee_bps": bps,
                "final_equity": result["final_equity"],
                "turnover": result["turnover"],
                "cost": result["cost"],
            }
        )

    frequency_rows: list[dict[str, object]] = []
    for step, label in [(1, "daily"), (5, "weekly"), (10, "biweekly")]:
        targets = _subsample_targets(base_targets, step=step)
        result = _scenario_run(targets, market, max_adv_pct=0.05, fee_bps=5, slippage_bps=1)
        frequency_rows.append(
            {
                "frequency": label,
                "step": step,
                "rows": len(targets),
                "final_equity": result["final_equity"],
                "turnover": result["turnover"],
                "cost": result["cost"],
            }
        )

    artifact_dir = ROOT / "artifacts"
    save_csv(pd.DataFrame(scheme_rows), artifact_dir / "scheme_compare.csv")
    save_csv(pd.DataFrame(liquidity_rows), artifact_dir / "liquidity_compare.csv")
    save_csv(pd.DataFrame(cost_rows), artifact_dir / "cost_sensitivity.csv")
    save_csv(pd.DataFrame(frequency_rows), artifact_dir / "rebalance_frequency.csv")

    scheme_df = pd.DataFrame(scheme_rows)
    liquidity_df = pd.DataFrame(liquidity_rows)
    cost_df = pd.DataFrame(cost_rows)
    frequency_df = pd.DataFrame(frequency_rows)
    liquidity_monotonic = bool(liquidity_df.sort_values("max_adv_pct")["turnover"].is_monotonic_increasing)
    cost_monotonic = bool(cost_df.sort_values("fee_bps")["cost"].is_monotonic_increasing)
    frequency_monotonic = bool(frequency_df.sort_values("step")["turnover"].is_monotonic_decreasing)
    blend_best = bool(scheme_df.loc[scheme_df["scheme"] == "blend_50_50", "final_equity"].iloc[0] >= scheme_df["final_equity"].max() * 0.98)
    steps = [
        "构造 Sharpe、逆波动率和 50/50 混合三种权重方案。",
        "以不同 max_adv_pct 测试流动性约束强弱。",
        "对手续费做 2/5/10 bps 敏感性分析。",
        "对日/周/半月再平衡频率做子采样比较。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = [
        "artifacts/scheme_compare.csv",
        "artifacts/liquidity_compare.csv",
        "artifacts/cost_sensitivity.csv",
        "artifacts/rebalance_frequency.csv",
    ]
    if liquidity_monotonic and cost_monotonic and frequency_monotonic and blend_best:
        status = "pass"
        conclusion = "混合权重、流动性约束、成本和频率对比均呈现预期方向。"
    else:
        status = "fail"
        conclusion = "组合优化的敏感性关系没有完全符合预期。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
