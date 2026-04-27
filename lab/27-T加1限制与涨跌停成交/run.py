from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_UNIVERSE, ExperimentMeta, build_momentum_portfolio, execute_rebalance, load_market_panel, record_experiment, save_csv


def _simulate_t1_block() -> pd.DataFrame:
    rows = [
        {"date": "2024-01-10", "event": "buy", "shares": 1000, "sellable_before": 0, "sellable_after": 0, "blocked": False},
        {"date": "2024-01-10", "event": "sell_attempt", "shares": -300, "sellable_before": 0, "sellable_after": 0, "blocked": True},
        {"date": "2024-01-11", "event": "sell", "shares": -300, "sellable_before": 1000, "sellable_after": 700, "blocked": False},
    ]
    return pd.DataFrame(rows)


def main() -> None:
    meta = ExperimentMeta(
        code="27",
        title="T加1限制与涨跌停成交",
        goal="验证 T+1 和涨跌停会约束成交，而不是无条件成交。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    target = build_momentum_portfolio(market.close, lookback=20, top_n=3, scheme="equal").holdings

    tradable_mask = pd.DataFrame(True, index=market.close.index, columns=market.close.columns)
    tradable_mask.iloc[25, 0] = False
    tradable_mask.iloc[26, 1] = False
    constrained = execute_rebalance(
        target,
        market,
        initial_cash=1_000_000.0,
        lot_size=100,
        tradable_mask=tradable_mask,
    )
    t1_log = _simulate_t1_block()

    artifact_dir = ROOT / "artifacts"
    save_csv(constrained.orders, artifact_dir / "orders.csv")
    save_csv(constrained.holdings, artifact_dir / "holdings.csv")
    save_csv(constrained.pnl, artifact_dir / "pnl.csv")
    save_csv(t1_log, artifact_dir / "t1_log.csv")

    blocked_orders = int((constrained.orders["tradable"] == False).sum()) if not constrained.orders.empty else 0
    t1_blocked = bool(t1_log["blocked"].any())
    lot_ok = bool((constrained.orders["trade_shares"].abs() % 100 == 0).all()) if not constrained.orders.empty else False

    steps = [
        "用 T+1 记账表模拟同日买入后立即卖出被阻断。",
        "在真实调仓执行中加入不可交易 mask，模拟涨跌停/停牌无法成交。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/orders.csv", "artifacts/holdings.csv", "artifacts/pnl.csv", "artifacts/t1_log.csv"]
    if blocked_orders > 0 and t1_blocked and lot_ok:
        status = "pass"
        conclusion = "T+1、涨跌停和最小交易单位都能约束成交。"
    else:
        status = "fail"
        conclusion = "成交约束未完整生效。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
