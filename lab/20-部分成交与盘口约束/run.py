from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import (
    DEFAULT_UNIVERSE,
    ExperimentMeta,
    build_momentum_portfolio,
    dynamic_slippage_cost,
    execute_rebalance,
    load_market_panel,
    record_experiment,
    save_csv,
)


def main() -> None:
    meta = ExperimentMeta(
        code="20",
        title="部分成交与盘口约束",
        goal="验证成交量约束会触发部分成交，而不是虚假满额成交。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    target = build_momentum_portfolio(market.close, lookback=20, top_n=3, scheme="equal").holdings
    relaxed = execute_rebalance(
        target,
        market,
        initial_cash=1_000_000.0,
        lot_size=100,
        max_adv_pct=0.20,
        slippage_fn=dynamic_slippage_cost,
    )
    constrained = execute_rebalance(
        target,
        market,
        initial_cash=1_000_000.0,
        lot_size=100,
        max_adv_pct=0.01,
        slippage_fn=dynamic_slippage_cost,
    )

    artifact_dir = ROOT / "artifacts"
    save_csv(relaxed.orders, artifact_dir / "relaxed_orders.csv")
    save_csv(relaxed.holdings, artifact_dir / "relaxed_holdings.csv")
    save_csv(constrained.orders, artifact_dir / "constrained_orders.csv")
    save_csv(constrained.holdings, artifact_dir / "constrained_holdings.csv")

    relaxed_fill = float(relaxed.holdings["fill_ratio"].mean()) if not relaxed.holdings.empty else 0.0
    constrained_fill = float(constrained.holdings["fill_ratio"].mean()) if not constrained.holdings.empty else 0.0
    constrained_error = float(constrained.holdings["weight_error"].abs().max()) if not constrained.holdings.empty else 1.0

    steps = [
        "以较宽和较紧的 ADV 约束分别执行同一组调仓指令。",
        "比较平均填充率和剩余权重误差，观察部分成交是否发生。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = [
        "artifacts/relaxed_orders.csv",
        "artifacts/relaxed_holdings.csv",
        "artifacts/constrained_orders.csv",
        "artifacts/constrained_holdings.csv",
    ]
    if constrained_fill < relaxed_fill and constrained_error > 0.0:
        status = "pass"
        conclusion = "成交量约束触发了部分成交，未出现虚假满额成交。"
    else:
        status = "fail"
        conclusion = "部分成交或盘口约束效果不明显。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
