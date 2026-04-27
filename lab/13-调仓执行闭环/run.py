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
    execute_rebalance,
    load_market_panel,
    record_experiment,
    save_csv,
)


def main() -> None:
    meta = ExperimentMeta(
        code="13",
        title="调仓执行闭环",
        goal="打通「目标权重 → 实际成交」。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    targets = build_momentum_portfolio(market.close, lookback=20, top_n=3, scheme="equal").holdings
    exec_run = execute_rebalance(targets, market, initial_cash=1_000_000.0, lot_size=100)

    orders_path = ROOT / "artifacts" / "orders.csv"
    holdings_path = ROOT / "artifacts" / "holdings.csv"
    pnl_path = ROOT / "artifacts" / "pnl.csv"
    save_csv(exec_run.orders, orders_path)
    save_csv(exec_run.holdings, holdings_path)
    save_csv(exec_run.pnl, pnl_path)

    max_error = float(exec_run.holdings["weight_error"].abs().max()) if not exec_run.holdings.empty else 1.0
    steps = [
        "按每日目标权重生成买卖数量。",
        f"面板来源：{market.source_mode}。",
        f"记录 {len(exec_run.orders)} 条调仓指令和 {len(exec_run.holdings)} 条持仓变化。",
        f"最大权重偏差 {max_error:.6f}。",
    ]
    artifacts = ["artifacts/orders.csv", "artifacts/holdings.csv", "artifacts/pnl.csv"]
    if not exec_run.holdings.empty and max_error <= 0.02:
        status = "pass"
        conclusion = "持仓可正确收敛到目标权重，误差在可接受范围内。"
    else:
        status = "fail"
        conclusion = "调仓执行未能稳定收敛到目标权重。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
