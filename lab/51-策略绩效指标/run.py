from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import (
    DEFAULT_UNIVERSE,
    ExperimentMeta,
    apply_costs,
    build_momentum_portfolio,
    compute_performance_metrics,
    compute_rolling_metrics,
    load_market_panel,
    record_experiment,
    save_csv,
)


def main() -> None:
    meta = ExperimentMeta(
        code="51",
        title="策略绩效指标",
        goal="补齐完整绩效指标、滚动绩效和成本敏感性结果。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20220103", "20240315")
    run = build_momentum_portfolio(market.close, lookback=20, top_n=3, scheme="equal")
    benchmark = market.close.pct_change().mean(axis=1).reindex(pd.to_datetime(run.pnl["date"])).fillna(0.0)
    gross_returns = pd.Series(run.pnl["gross_return"].values, index=pd.to_datetime(run.pnl["date"]))
    turnover = pd.Series(run.pnl["turnover"].values, index=pd.to_datetime(run.pnl["date"]))

    metric_rows: list[pd.DataFrame] = []
    rolling_rows: list[pd.DataFrame] = []
    sensitivity_rows: list[dict[str, object]] = []
    for fee_bps in [0, 2, 5, 10]:
        if fee_bps == 0:
            adjusted = run.pnl.copy()
            adjusted["net_return"] = adjusted["gross_return"]
        else:
            adjusted = apply_costs(run.pnl, fee_bps=fee_bps, slippage_bps=1)
        returns = pd.Series(adjusted["net_return"].values if "net_return" in adjusted.columns else adjusted["gross_return"].values, index=pd.to_datetime(adjusted["date"]))
        metrics = compute_performance_metrics(returns, benchmark=benchmark.reindex(returns.index), turnover=turnover.reindex(returns.index))
        metrics["fee_bps"] = fee_bps
        metric_rows.append(metrics)
        rolling_rows.append(compute_rolling_metrics(returns, benchmark=benchmark.reindex(returns.index), window=21, label=f"monthly_{fee_bps}bps"))
        rolling_rows.append(compute_rolling_metrics(returns, benchmark=benchmark.reindex(returns.index), window=63, label=f"quarterly_{fee_bps}bps"))
        sensitivity_rows.append(
            {
                "fee_bps": fee_bps,
                "final_equity": float((1.0 + returns.fillna(0.0)).cumprod().iloc[-1]) if not returns.empty else np.nan,
                "avg_turnover": float(turnover.mean()) if not turnover.empty else np.nan,
                "sharpe": float(metrics["sharpe"].iloc[0]),
                "mdd": float(metrics["mdd"].iloc[0]),
            }
        )

    metrics_df = pd.concat(metric_rows, ignore_index=True) if metric_rows else pd.DataFrame()
    rolling_df = pd.concat(rolling_rows, ignore_index=True) if rolling_rows else pd.DataFrame()
    sensitivity_df = pd.DataFrame(sensitivity_rows)

    artifact_dir = ROOT / "artifacts"
    save_csv(metrics_df, artifact_dir / "metrics.csv")
    save_csv(rolling_df, artifact_dir / "rolling_metrics.csv")
    save_csv(sensitivity_df, artifact_dir / "sensitivity.csv")

    metric_columns = ["sharpe", "mdd", "sortino", "beta", "alpha", "skew", "kurtosis", "turnover", "win_rate", "cvar_5"]
    metrics_ok = bool(set(metric_columns).issubset(metrics_df.columns) and metrics_df[metric_columns].notna().any().all()) if not metrics_df.empty else False
    rolling_ok = bool(not rolling_df.empty and rolling_df["label"].nunique() >= 2)
    sensitivity_ok = bool(sensitivity_df["fee_bps"].is_monotonic_increasing and sensitivity_df["final_equity"].nunique() >= 2)
    steps = [
        "基于同一策略收益序列，补齐 Sharpe、MDD、Sortino、Beta、Alpha、Skew、Kurtosis、Turnover、WinRate 等指标。",
        "分别按 21 日和 63 日窗口计算滚动绩效。",
        "对交易成本做 0/2/5/10 bps 敏感性分析。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/metrics.csv", "artifacts/rolling_metrics.csv", "artifacts/sensitivity.csv"]
    if metrics_ok and rolling_ok and sensitivity_ok:
        status = "pass"
        conclusion = "完整绩效指标与滚动绩效均可稳定输出，成本变化也能拉开差异。"
    else:
        status = "fail"
        conclusion = "绩效指标或滚动统计存在缺口。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
