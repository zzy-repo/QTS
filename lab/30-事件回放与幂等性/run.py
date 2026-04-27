from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
from pandas.testing import assert_frame_equal

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_UNIVERSE, ExperimentMeta, build_momentum_portfolio, execute_rebalance, load_market_panel, record_experiment, save_csv


def _replay_from_orders(orders: pd.DataFrame, market_close: pd.DataFrame, initial_cash: float = 1_000_000.0) -> pd.DataFrame:
    cash = float(initial_cash)
    shares = pd.Series(dtype=float)
    rows: list[dict[str, object]] = []
    order_dates = list(pd.to_datetime(orders["date"]).drop_duplicates().sort_values())
    for idx, date in enumerate(order_dates):
        date_ts = pd.Timestamp(date)
        day_orders = orders[pd.to_datetime(orders["date"]) == date_ts]
        price_row = market_close.loc[date_ts]
        current = shares.reindex(price_row.index).fillna(0.0)
        for _, row in day_orders.iterrows():
            symbol = row["symbol"]
            trade_shares = float(row["trade_shares"])
            cash -= trade_shares * float(price_row[symbol])
            current.loc[symbol] = current.get(symbol, 0.0) + trade_shares
        shares = current
        if idx < len(order_dates) - 1:
            next_date = pd.Timestamp(order_dates[idx + 1])
            next_prices = market_close.loc[next_date]
            equity = cash + float((shares.reindex(next_prices.index).fillna(0.0) * next_prices).sum())
            rows.append(
                {
                    "date": next_date.strftime("%Y-%m-%d"),
                    "signal_date": date_ts.strftime("%Y-%m-%d"),
                    "cash": cash,
                    "equity": equity,
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    meta = ExperimentMeta(
        code="30",
        title="事件回放与幂等性",
        goal="验证订单事件可回放，并且重复回放结果一致。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    target = build_momentum_portfolio(market.close, lookback=20, top_n=3, scheme="equal").holdings
    exec_run = execute_rebalance(target, market, initial_cash=1_000_000.0, lot_size=100)
    replay_a = _replay_from_orders(exec_run.orders, market.close)
    replay_b = _replay_from_orders(exec_run.orders, market.close)

    artifact_dir = ROOT / "artifacts"
    save_csv(exec_run.orders, artifact_dir / "orders.csv")
    save_csv(exec_run.holdings, artifact_dir / "holdings.csv")
    save_csv(exec_run.pnl, artifact_dir / "pnl.csv")
    save_csv(replay_a, artifact_dir / "replay_a.csv")
    save_csv(replay_b, artifact_dir / "replay_b.csv")

    replay_ok = bool(replay_a.equals(replay_b))
    replay_equity = replay_a[["date", "equity"]].reset_index(drop=True)
    original_equity = exec_run.pnl[["date", "equity"]].reset_index(drop=True)
    try:
        assert_frame_equal(replay_equity, original_equity, check_dtype=False, atol=1e-10, rtol=1e-10)
        final_match = True
    except AssertionError:
        final_match = False
    steps = [
        "把订单和成交结果写成事件序列，再按顺序回放。",
        "重复回放两次，检查幂等性和最终权益一致性。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = [
        "artifacts/orders.csv",
        "artifacts/holdings.csv",
        "artifacts/pnl.csv",
        "artifacts/replay_a.csv",
        "artifacts/replay_b.csv",
    ]
    if replay_ok and final_match:
        status = "pass"
        conclusion = "事件可以回放，重复执行结果一致。"
    else:
        status = "fail"
        conclusion = "事件回放或幂等性未达到预期。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
