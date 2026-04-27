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
    load_market_panel,
    momentum_signal,
    record_experiment,
    save_csv,
)


def _orchestrate(signals, optimizer, executor, market):
    target = optimizer.run(signals)[["date", "symbol", "weight"]]
    return executor.run(target, market)


def main() -> None:
    meta = ExperimentMeta(
        code="40",
        title="执行环境切换",
        goal="验证回测、模拟和近实盘执行可以通过同一适配器接口切换。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    data = StrategyInput(close=market.close, volume=market.volume, amount=market.amount, lookback=20, top_n=3)
    signals = momentum_signal(data)
    optimizer = build_optimizers()["score"]
    adapters = build_execution_adapters()

    backtest = _orchestrate(signals, optimizer, adapters["backtest"], market)
    sim = _orchestrate(signals, optimizer, adapters["sim"], market)
    paper = _orchestrate(signals, optimizer, adapters["paper"], market)

    artifact_dir = ROOT / "artifacts"
    save_csv(backtest.pnl, artifact_dir / "backtest_pnl.csv")
    save_csv(sim.pnl, artifact_dir / "sim_pnl.csv")
    save_csv(paper.pnl, artifact_dir / "paper_pnl.csv")

    same_schema = set(backtest.orders.columns) == set(sim.orders.columns) == set(paper.orders.columns)
    env_variation = len(
        {
            round(float(run.pnl["slippage_cost"].sum()), 6) if "slippage_cost" in run.pnl.columns and not run.pnl.empty else 0.0
            for run in [backtest, sim, paper]
        }
    ) > 1
    steps = [
        "保持策略和优化器不变，只切换执行适配器。",
        "对比回测、模拟和近实盘三种执行环境的输出。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/backtest_pnl.csv", "artifacts/sim_pnl.csv", "artifacts/paper_pnl.csv"]
    if same_schema and env_variation:
        status = "pass"
        conclusion = "执行环境可以通过适配器切换，其余模块不需要改动。"
    else:
        status = "fail"
        conclusion = "执行环境切换未达到预期。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
