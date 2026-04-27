from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
from pandas.testing import assert_frame_equal

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import (
    DEFAULT_UNIVERSE,
    ExperimentMeta,
    apply_costs,
    build_momentum_portfolio,
    compute_metrics,
    execute_rebalance,
    load_market_panel,
    record_experiment,
    save_csv,
)


def main() -> None:
    meta = ExperimentMeta(
        code="17",
        title="结果持久化闭环",
        goal="保证策略结果可追溯。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    target = build_momentum_portfolio(market.close, lookback=20, top_n=3, scheme="equal").holdings
    exec_run = execute_rebalance(target, market, initial_cash=1_000_000.0, lot_size=100)
    costed = apply_costs(exec_run.pnl, fee_bps=5, slippage_bps=1)
    metrics = compute_metrics(costed["net_return"])

    orders_path = ROOT / "artifacts" / "orders.csv"
    holdings_path = ROOT / "artifacts" / "holdings.csv"
    pnl_path = ROOT / "artifacts" / "pnl.csv"
    metrics_path = ROOT / "artifacts" / "metrics.csv"
    manifest_path = ROOT / "artifacts" / "manifest.txt"
    save_csv(exec_run.orders, orders_path)
    save_csv(exec_run.holdings, holdings_path)
    save_csv(costed, pnl_path)
    save_csv(metrics, metrics_path)

    replay_orders = pd.read_csv(orders_path, dtype={"date": "string", "symbol": "string"})
    replay_holdings = pd.read_csv(holdings_path, dtype={"date": "string", "symbol": "string"})
    replay_pnl = pd.read_csv(pnl_path, dtype={"date": "string", "signal_date": "string"})
    replay_metrics = pd.read_csv(metrics_path)
    try:
        assert_frame_equal(
            replay_orders,
            exec_run.orders.reset_index(drop=True),
            check_dtype=False,
            check_like=False,
            atol=1e-10,
            rtol=1e-10,
        )
        assert_frame_equal(
            replay_holdings,
            exec_run.holdings.reset_index(drop=True),
            check_dtype=False,
            check_like=False,
            atol=1e-10,
            rtol=1e-10,
        )
        assert_frame_equal(
            replay_pnl,
            costed.reset_index(drop=True),
            check_dtype=False,
            check_like=False,
            atol=1e-10,
            rtol=1e-10,
        )
        assert_frame_equal(
            replay_metrics,
            metrics.reset_index(drop=True),
            check_dtype=False,
            check_like=False,
            atol=1e-10,
            rtol=1e-10,
        )
        replay_ok = True
    except AssertionError:
        replay_ok = False
    manifest_path.write_text(
        "\n".join(
            [
                f"orders={len(exec_run.orders)}",
                f"holdings={len(exec_run.holdings)}",
                f"pnl={len(costed)}",
                f"metrics={len(metrics)}",
                f"replay_ok={replay_ok}",
            ]
        ),
        encoding="utf-8",
    )

    steps = [
        "落盘持仓、交易、PnL、指标四类结果。",
        f"面板来源：{market.source_mode}。",
        "从磁盘回放并校验历史状态是否一致。",
    ]
    artifacts = [
        "artifacts/orders.csv",
        "artifacts/holdings.csv",
        "artifacts/pnl.csv",
        "artifacts/metrics.csv",
        "artifacts/manifest.txt",
    ]
    if replay_ok:
        status = "pass"
        conclusion = "数据完整、无缺失、可复算。"
    else:
        status = "fail"
        conclusion = "持久化结果回放不一致。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
