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
    load_market_panel,
    momentum_signal,
    record_experiment,
    save_csv,
    trend_follow_signal,
    validate_strategy_output,
)


def main() -> None:
    meta = ExperimentMeta(
        code="31",
        title="策略层解耦",
        goal="验证策略只做输入到目标权重的纯变换。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    data = StrategyInput(close=market.close, volume=market.volume, amount=market.amount, lookback=20, top_n=3)
    first = momentum_signal(data)
    second = momentum_signal(data)
    alt = trend_follow_signal(data)

    artifact_dir = ROOT / "artifacts"
    save_csv(first, artifact_dir / "momentum.csv")
    save_csv(alt, artifact_dir / "trend.csv")

    pure_ok = first.equals(second)
    validation_ok = not validate_strategy_output(first) and not validate_strategy_output(alt)
    no_execution_fields = "cash" not in first.columns and "positions" not in first.columns
    steps = [
        "把行情输入封装为 StrategyInput，只让策略返回信号与权重。",
        "重复调用同一策略，检查输出是否稳定。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/momentum.csv", "artifacts/trend.csv"]
    if pure_ok and validation_ok and no_execution_fields:
        status = "pass"
        conclusion = "策略层只做纯函数变换，未触碰资金或执行状态。"
    else:
        status = "fail"
        conclusion = "策略层解耦未达到预期。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
