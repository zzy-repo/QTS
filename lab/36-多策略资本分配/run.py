from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import (
    DEFAULT_UNIVERSE,
    ExperimentMeta,
    StrategyInput,
    allocate_capital,
    load_market_panel,
    momentum_signal,
    record_experiment,
    save_csv,
    trend_follow_signal,
)


def main() -> None:
    meta = ExperimentMeta(
        code="36",
        title="多策略资本分配",
        goal="验证 strategy -> allocator -> executor 的中间分层。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    data = StrategyInput(close=market.close, volume=market.volume, amount=market.amount, lookback=20, top_n=3)
    mkt = momentum_signal(data).copy()
    mkt["strategy"] = "momentum"
    trend = trend_follow_signal(data).copy()
    trend["strategy"] = "trend"
    combined = pd.concat([mkt, trend], ignore_index=True)
    alloc = allocate_capital(combined, total_cash=1_000_000.0, caps={"momentum": 0.7, "trend": 0.6})

    artifact_dir = ROOT / "artifacts"
    save_csv(combined, artifact_dir / "strategy_signals.csv")
    save_csv(alloc.allocation, artifact_dir / "allocation.csv")

    allocation_sum = float(alloc.allocation["allocated_cash"].sum()) if not alloc.allocation.empty else 0.0
    namespaced = "strategy" in combined.columns and "allocated_cash" in alloc.allocation.columns
    capped = bool((alloc.allocation["allocated_cash"] >= 0).all()) if not alloc.allocation.empty else False
    steps = [
        "把两种策略信号合并，再交给独立 allocator 分配资金。",
        "验证策略层和资金分配层之间有清晰边界。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/strategy_signals.csv", "artifacts/allocation.csv"]
    if namespaced and capped and allocation_sum <= 1_000_000.0 + 1e-6:
        status = "pass"
        conclusion = "多策略资本分配层可独立工作。"
    else:
        status = "fail"
        conclusion = "多策略分配未达到预期。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
