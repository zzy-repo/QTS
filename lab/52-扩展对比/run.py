from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import (
    ExperimentMeta,
    apply_costs,
    execute_rebalance,
    load_market_panel,
    record_experiment,
    save_csv,
)
from shared.feasibility import compute_performance_metrics


def _build_targets(market, lookback: int, mode: str) -> pd.DataFrame:
    close = market.close
    returns = close.pct_change()
    rows: list[dict[str, object]] = []
    for date in close.index[lookback:-1]:
        window = returns.loc[:date].tail(lookback)
        if window.empty:
            continue
        if mode == "equal":
            weights = pd.Series(1.0 / len(close.columns), index=close.columns)
        elif mode == "cap":
            cap_proxy = market.amount.loc[:date].tail(lookback).mean().reindex(close.columns).fillna(0.0)
            weights = cap_proxy / cap_proxy.sum() if cap_proxy.sum() > 0 else pd.Series(1.0 / len(close.columns), index=close.columns)
        elif mode == "markowitz":
            cov = window.cov().to_numpy(dtype=float)
            cov = cov + np.eye(len(close.columns)) * 1e-6
            ones = np.ones(len(close.columns))
            inv = np.linalg.pinv(cov)
            raw = inv @ ones
            denom = float(ones @ raw)
            if denom > 0 and np.isfinite(denom):
                weights = pd.Series(np.clip(raw / denom, 0.0, None), index=close.columns)
                if weights.sum() > 0:
                    weights = weights / weights.sum()
                else:
                    weights = pd.Series(1.0 / len(close.columns), index=close.columns)
            else:
                weights = pd.Series(1.0 / len(close.columns), index=close.columns)
        else:
            momentum = close.pct_change(lookback).loc[date].reindex(close.columns).fillna(0.0)
            positive = momentum.clip(lower=0.0)
            if positive.sum() <= 0:
                weights = pd.Series(1.0 / len(close.columns), index=close.columns)
            else:
                weights = positive / positive.sum()
                equal = pd.Series(1.0 / len(close.columns), index=close.columns)
                weights = 0.6 * weights + 0.4 * equal
                weights = weights / weights.sum()
        for symbol, weight in weights.items():
            rows.append({"date": date.strftime("%Y-%m-%d"), "symbol": symbol, "weight": float(weight), "strategy": mode})
    return pd.DataFrame(rows)


def _run_portfolio(targets: pd.DataFrame, market) -> pd.DataFrame:
    execution = execute_rebalance(targets, market, initial_cash=1_000_000.0, lot_size=100, max_adv_pct=0.05)
    costed = apply_costs(execution.pnl, fee_bps=5, slippage_bps=1)
    return costed


def main() -> None:
    meta = ExperimentMeta(
        code="52",
        title="扩展对比",
        goal="比较不同基准组合、Alpha 增量价值和多子宇宙适应性。",
        root=ROOT,
    )
    universe_sets = {
        "large_proxy": ["000001", "000002", "600519"],
        "mid_proxy": ["000002", "600519", "601318"],
        "growth_proxy": ["600519", "601318", "300750"],
    }
    strategies = ["equal", "cap", "markowitz", "alpha"]

    universe_rows: list[dict[str, object]] = []
    alpha_delta_rows: list[dict[str, object]] = []
    benchmark_rows: list[dict[str, object]] = []
    for universe_name, symbols in universe_sets.items():
        market = load_market_panel(symbols, "20220103", "20240315")
        benchmark = market.close.pct_change().mean(axis=1).fillna(0.0)
        universe_result: dict[str, dict[str, object]] = {}
        for strategy in strategies:
            targets = _build_targets(market, lookback=20, mode=strategy)
            costed = _run_portfolio(targets, market)
            returns = pd.Series(costed["net_return"].values, index=pd.to_datetime(costed["date"]))
            turnover = pd.Series(costed["turnover"].values, index=pd.to_datetime(costed["date"])) if "turnover" in costed.columns else pd.Series(dtype=float)
            metrics = compute_performance_metrics(returns, benchmark=benchmark.reindex(returns.index), turnover=turnover.reindex(returns.index))
            row = {
                "universe": universe_name,
                "strategy": strategy,
                "final_equity": float(costed["net_equity"].iloc[-1]) if not costed.empty else np.nan,
                "sharpe": float(metrics["sharpe"].iloc[0]),
                "mdd": float(metrics["mdd"].iloc[0]),
                "alpha": float(metrics["alpha"].iloc[0]),
                "beta": float(metrics["beta"].iloc[0]),
            }
            benchmark_rows.append(row)
            universe_rows.append(row)
            universe_result[strategy] = row
        if "equal" in universe_result and "alpha" in universe_result:
            alpha_delta_rows.append(
                {
                    "universe": universe_name,
                    "delta_final_equity": universe_result["alpha"]["final_equity"] - universe_result["equal"]["final_equity"],
                    "delta_sharpe": universe_result["alpha"]["sharpe"] - universe_result["equal"]["sharpe"],
                    "delta_alpha": universe_result["alpha"]["alpha"] - universe_result["equal"]["alpha"],
                }
            )

    benchmark_df = pd.DataFrame(benchmark_rows)
    universe_df = pd.DataFrame(universe_rows)
    alpha_delta_df = pd.DataFrame(alpha_delta_rows)

    artifact_dir = ROOT / "artifacts"
    save_csv(benchmark_df, artifact_dir / "benchmark_compare.csv")
    save_csv(universe_df, artifact_dir / "universe_compare.csv")
    save_csv(alpha_delta_df, artifact_dir / "alpha_delta.csv")

    alpha_positive = bool((alpha_delta_df[["delta_final_equity", "delta_sharpe"]].fillna(0.0) > 0).any().any()) if not alpha_delta_df.empty else False
    universe_coverage = bool(universe_df["universe"].nunique() >= 3 and universe_df["strategy"].nunique() >= 4) if not universe_df.empty else False
    steps = [
        "在三个代理宇宙上对 Equal、Cap、Markowitz 和 Alpha 四种组合做对比。",
        "把 Alpha 方案与 Equal 方案做增量价值比较。",
        "同时输出多子宇宙的绩效，观察跨市场适应性。",
        "由于当前数据没有真实板块标签，这里使用宇宙切片作为适配代理。",
    ]
    artifacts = ["artifacts/benchmark_compare.csv", "artifacts/universe_compare.csv", "artifacts/alpha_delta.csv"]
    if alpha_positive and universe_coverage:
        status = "pass"
        conclusion = "Alpha 方案在部分代理宇宙上带来增量价值，且多宇宙表现可对比。"
    else:
        status = "fail"
        conclusion = "扩展对比未体现出稳定的增量价值或适配差异。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
