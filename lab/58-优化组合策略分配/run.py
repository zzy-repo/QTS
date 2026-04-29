from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
REPO_ROOT = LAB_ROOT.parent
sys.path.insert(0, str(LAB_ROOT))
sys.path.insert(0, str(REPO_ROOT))

from shared import (
    DEFAULT_UNIVERSE,
    ExperimentMeta,
    build_strategy_allocation_study,
    equal_allocate_strategy_capital,
    load_market_panel,
    optimized_allocate_strategy_capital,
    portfolio_utility,
    record_experiment,
    risk_parity_allocate_strategy_capital,
    save_csv,
)


def _summary_row(name: str, weights: pd.Series, expected_returns: pd.Series, covariance: pd.DataFrame) -> dict[str, object]:
    aligned = weights.reindex(expected_returns.index).fillna(0.0)
    cov = covariance.reindex(index=aligned.index, columns=aligned.index).fillna(0.0)
    expected = float(aligned.to_numpy(dtype=float) @ expected_returns.to_numpy(dtype=float))
    risk = float(aligned.to_numpy(dtype=float) @ cov.to_numpy(dtype=float) @ aligned.to_numpy(dtype=float))
    utility = float(portfolio_utility(aligned, expected_returns, covariance))
    return {
        "scheme": name,
        "expected_return": expected,
        "variance": risk,
        "utility": utility,
    }


def main() -> None:
    meta = ExperimentMeta(
        code="58",
        title="优化组合策略分配",
        goal="验证策略层资金可依据预期收益和协方差做长仓优化组合分配。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20230102", "20240315")
    study = build_strategy_allocation_study(market, lookback=20, top_n=3, history_window=60)
    optimized, mode, expected_returns, covariance = optimized_allocate_strategy_capital(
        study.strategy_returns,
        total_cash=1_000_000.0,
        history_window=60,
        risk_aversion=4.0,
    )
    equal = equal_allocate_strategy_capital(study.signals, total_cash=1_000_000.0)
    risk_parity = risk_parity_allocate_strategy_capital(study.strategy_returns, total_cash=1_000_000.0, history_window=60)

    optimized_weights = optimized.allocation.set_index("strategy")["weight"] if not optimized.allocation.empty else pd.Series(dtype=float)
    equal_weights = equal.allocation.set_index("strategy")["weight"] if not equal.allocation.empty else pd.Series(dtype=float)
    rp_weights = risk_parity.allocation.set_index("strategy")["weight"] if not risk_parity.allocation.empty else pd.Series(dtype=float)
    diagnostics = pd.DataFrame(
        [
            _summary_row("optimized", optimized_weights, expected_returns, covariance),
            _summary_row("equal", equal_weights, expected_returns, covariance),
            _summary_row("risk_parity", rp_weights, expected_returns, covariance),
        ]
    )

    artifact_dir = ROOT / "artifacts"
    save_csv(study.strategy_returns, artifact_dir / "strategy_returns.csv")
    save_csv(expected_returns.rename("expected_return").reset_index().rename(columns={"index": "strategy"}), artifact_dir / "expected_returns.csv")
    save_csv(optimized.allocation.assign(mode=mode), artifact_dir / "allocation.csv")
    save_csv(diagnostics, artifact_dir / "objective_compare.csv")

    optimized_utility = float(diagnostics.loc[diagnostics["scheme"] == "optimized", "utility"].iloc[0]) if not diagnostics.empty else float("-inf")
    baseline_utility = float(diagnostics.loc[diagnostics["scheme"] != "optimized", "utility"].max()) if len(diagnostics) > 1 else float("-inf")
    fully_allocated = abs(float(optimized_weights.sum()) - 1.0) <= 1e-6 if not optimized_weights.empty else False
    steps = [
        "从近 60 期策略收益估计预期收益与协方差。",
        "求解 long-only 均值方差候选权重，并与最小方差、等权候选做效用比较。",
        f"输出最优候选模式：{mode}。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = [
        "artifacts/strategy_returns.csv",
        "artifacts/expected_returns.csv",
        "artifacts/allocation.csv",
        "artifacts/objective_compare.csv",
    ]
    if len(optimized_weights) >= 3 and optimized_utility >= baseline_utility - 1e-12 and fully_allocated and optimized.cash_left <= 1e-6:
        status = "pass"
        conclusion = "优化组合分配可解，样本内效用不弱于等权和风险平价基线。"
    else:
        status = "fail"
        conclusion = "优化组合分配未稳定优于基线，仍需继续调参与约束设计。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
