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
    load_market_panel,
    record_experiment,
    risk_contributions,
    risk_parity_allocate_strategy_capital,
    save_csv,
)


def main() -> None:
    meta = ExperimentMeta(
        code="57",
        title="风险平价策略分配",
        goal="验证策略层资金可依据策略收益协方差做风险平价分配。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20230102", "20240315")
    study = build_strategy_allocation_study(market, lookback=20, top_n=3, history_window=60)
    allocation = risk_parity_allocate_strategy_capital(study.strategy_returns, total_cash=1_000_000.0, history_window=60)

    weights = allocation.allocation.set_index("strategy")["weight"] if not allocation.allocation.empty else pd.Series(dtype=float)
    contributions = risk_contributions(weights, study.covariance).rename("risk_contribution")
    diagnostics = (
        allocation.allocation.merge(contributions.reset_index().rename(columns={"index": "strategy"}), on="strategy", how="left")
        if not allocation.allocation.empty
        else pd.DataFrame(columns=["strategy", "weight", "allocated_cash", "risk_contribution"])
    )

    artifact_dir = ROOT / "artifacts"
    save_csv(study.strategy_returns, artifact_dir / "strategy_returns.csv")
    save_csv(study.covariance.reset_index().rename(columns={"index": "strategy"}), artifact_dir / "covariance.csv")
    save_csv(diagnostics, artifact_dir / "allocation.csv")

    contrib_span = float(contributions.max() - contributions.min()) if not contributions.empty else float("inf")
    fully_allocated = abs(float(weights.sum()) - 1.0) <= 1e-6 if not weights.empty else False
    steps = [
        "从策略日收益面板估计近 60 期协方差矩阵，并做轻度对角收缩。",
        "通过迭代法求解 long-only 风险平价权重。",
        "检查各策略风险贡献是否收敛到近似相等。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = [
        "artifacts/strategy_returns.csv",
        "artifacts/covariance.csv",
        "artifacts/allocation.csv",
    ]
    if len(weights) >= 3 and contrib_span <= 0.08 and fully_allocated and allocation.cash_left <= 1e-6:
        status = "pass"
        conclusion = "风险平价分配可解，策略间风险贡献已收敛到接近均衡。"
    else:
        status = "fail"
        conclusion = "风险平价分配未能稳定收敛到可接受的风险贡献均衡。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
