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
    optimized = optimizer.run(signals)
    target = optimized.rename(columns={"optimizer": "strategy"})[["date", "symbol", "weight"]]
    exec_run = executor.run(target, market)
    return optimized, exec_run


def main() -> None:
    meta = ExperimentMeta(
        code="39",
        title="模块替换与接口稳定性",
        goal="验证核心模块替换时上层编排无需改动。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    data = StrategyInput(close=market.close, volume=market.volume, amount=market.amount, lookback=20, top_n=3)
    signals = momentum_signal(data)
    optimizers = build_optimizers()
    executor = build_execution_adapters()["backtest"]

    equal_opt, equal_exec = _orchestrate(signals, optimizers["equal"], executor, market)
    score_opt, score_exec = _orchestrate(signals, optimizers["score"], executor, market)

    artifact_dir = ROOT / "artifacts"
    save_csv(equal_opt, artifact_dir / "equal_optimizer.csv")
    save_csv(score_opt, artifact_dir / "score_optimizer.csv")
    save_csv(equal_exec.pnl, artifact_dir / "equal_pnl.csv")
    save_csv(score_exec.pnl, artifact_dir / "score_pnl.csv")

    orders_schema_ok = set(equal_exec.orders.columns) == set(score_exec.orders.columns)
    pnl_schema_ok = set(equal_exec.pnl.columns) == set(score_exec.pnl.columns)
    wiring_only = equal_opt.columns.tolist() == score_opt.columns.tolist()
    steps = [
        "保持同一编排函数不变，只替换 optimizer 模块。",
        "用两个不同 optimizer 输出同一份上层目标权重接口。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = [
        "artifacts/equal_optimizer.csv",
        "artifacts/score_optimizer.csv",
        "artifacts/equal_pnl.csv",
        "artifacts/score_pnl.csv",
    ]
    if orders_schema_ok and pnl_schema_ok and wiring_only:
        status = "pass"
        conclusion = "核心模块可替换，上层只需要改 wiring。"
    else:
        status = "fail"
        conclusion = "模块替换后接口不稳定。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
