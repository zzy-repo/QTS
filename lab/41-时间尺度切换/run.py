from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import (
    DEFAULT_UNIVERSE,
    ExperimentMeta,
    StrategyInput,
    build_execution_adapters,
    build_optimizers,
    expand_to_ticks,
    load_market_panel,
    momentum_signal,
    record_experiment,
    save_csv,
)


def main() -> None:
    meta = ExperimentMeta(
        code="41",
        title="时间尺度切换",
        goal="验证日频到 tick-like 尺度切换只影响数据层和参数层。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    tick_close = expand_to_ticks(market.close, bars_per_day=3)
    tick_volume = expand_to_ticks(market.volume, bars_per_day=3)
    tick_amount = expand_to_ticks(market.amount, bars_per_day=3)

    daily_data = StrategyInput(close=market.close, volume=market.volume, amount=market.amount, lookback=20, top_n=3)
    tick_data = StrategyInput(close=tick_close, volume=tick_volume, amount=tick_amount, lookback=60, top_n=3)
    optimizer = build_optimizers()["equal"]
    executor = build_execution_adapters()["backtest"]

    daily_signals = momentum_signal(daily_data)
    tick_signals = momentum_signal(tick_data)
    daily_exec = executor.run(optimizer.run(daily_signals)[["date", "symbol", "weight"]], market)
    tick_market = type(market)(close=tick_close, volume=tick_volume, amount=tick_amount, source_mode=market.source_mode)
    tick_exec = executor.run(optimizer.run(tick_signals)[["date", "symbol", "weight"]], tick_market)

    artifact_dir = ROOT / "artifacts"
    save_csv(daily_signals, artifact_dir / "daily_signals.csv")
    save_csv(tick_signals, artifact_dir / "tick_signals.csv")
    save_csv(daily_exec.pnl, artifact_dir / "daily_pnl.csv")
    save_csv(tick_exec.pnl, artifact_dir / "tick_pnl.csv")

    data_layer_ok = len(tick_signals) >= len(daily_signals)
    parameter_only = daily_signals.columns.tolist() == tick_signals.columns.tolist()
    steps = [
        "把同一策略分别跑在日频和 tick-like 数据上。",
        "只调整数据层和 lookback 参数，不改策略函数或执行器。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/daily_signals.csv", "artifacts/tick_signals.csv", "artifacts/daily_pnl.csv", "artifacts/tick_pnl.csv"]
    if data_layer_ok and parameter_only:
        status = "pass"
        conclusion = "时间尺度切换只影响数据和参数层。"
    else:
        status = "fail"
        conclusion = "时间尺度切换仍耦合到上层逻辑。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
