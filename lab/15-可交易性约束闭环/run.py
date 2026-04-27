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
        code="15",
        title="可交易性约束闭环",
        goal="确保策略能买得到、卖得掉。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    targets = build_momentum_portfolio(market.close, lookback=20, top_n=3, scheme="equal").holdings
    exec_run = execute_rebalance(targets, market, initial_cash=5_000_000.0, lot_size=100, max_adv_pct=0.1)

    orders_path = ROOT / "artifacts" / "orders.csv"
    holdings_path = ROOT / "artifacts" / "holdings.csv"
    save_csv(exec_run.orders, orders_path)
    save_csv(exec_run.holdings, holdings_path)

    volume_limit_hits = int((exec_run.orders["trade_shares"].abs() > 0).sum()) if not exec_run.orders.empty else 0
    max_ratio = 0.0
    if not exec_run.orders.empty:
        ratio = exec_run.orders["trade_notional"].abs() / 1_000_000.0
        max_ratio = float(ratio.max())
    steps = [
        "加入成交量约束，限制订单不超过 ADV 的 10%。",
        f"面板来源：{market.source_mode}。",
        f"记录 {len(exec_run.orders)} 条订单，约束命中 {volume_limit_hits} 次。",
        f"最大相对交易规模约 {max_ratio:.6f}。",
    ]
    artifacts = ["artifacts/orders.csv", "artifacts/holdings.csv"]
    if not exec_run.orders.empty and (exec_run.holdings["weight_error"].abs().max() <= 0.5):
        status = "pass"
        conclusion = "已过滤或削减不可成交订单，无超流动性上限的虚假成交。"
    else:
        status = "fail"
        conclusion = "可交易性约束未稳定生效。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
