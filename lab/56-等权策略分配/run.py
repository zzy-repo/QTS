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
    record_experiment,
    save_csv,
)


def main() -> None:
    meta = ExperimentMeta(
        code="56",
        title="等权策略分配",
        goal="验证策略层资金可按等权方式稳定分配，并与策略信号强弱隔离。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20230102", "20240315")
    study = build_strategy_allocation_study(market, lookback=20, top_n=3, history_window=40)
    allocation = equal_allocate_strategy_capital(study.signals, total_cash=1_000_000.0)

    artifact_dir = ROOT / "artifacts"
    save_csv(study.signals, artifact_dir / "strategy_signals.csv")
    save_csv(study.strategy_returns, artifact_dir / "strategy_returns.csv")
    save_csv(allocation.allocation, artifact_dir / "allocation.csv")

    weights = allocation.allocation["weight"] if not allocation.allocation.empty else pd.Series(dtype=float)
    weight_span = float(weights.max() - weights.min()) if not weights.empty else float("inf")
    fully_allocated = abs(float(weights.sum()) - 1.0) <= 1e-6 if not weights.empty else False
    steps = [
        "从同一市场面板构造 momentum、trend、defensive 三组策略信号与下一日收益。",
        "仅使用策略集合，不读取 score 强弱，直接按策略个数做等权分配。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = [
        "artifacts/strategy_signals.csv",
        "artifacts/strategy_returns.csv",
        "artifacts/allocation.csv",
    ]
    if len(allocation.allocation) >= 3 and weight_span <= 1e-9 and fully_allocated and allocation.cash_left <= 1e-6:
        status = "pass"
        conclusion = "等权分配可独立工作，策略强弱不会影响策略层资金切分。"
    else:
        status = "fail"
        conclusion = "等权分配未能稳定输出满额且均匀的策略层资金。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
