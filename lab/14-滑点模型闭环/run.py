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


def _slippage_factory(market):
    def _cost(trade_notional: float, adv_notional: float, volatility: float) -> float:
        return dynamic_slippage_cost(
            trade_notional,
            adv_notional,
            volatility,
            base_bps=1.0,
            participation_scale=0.040,
            vol_scale=0.20,
        )

    return _cost


def main() -> None:
    meta = ExperimentMeta(
        code="14",
        title="滑点模型闭环",
        goal="引入更真实的成交价格偏移。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    targets = build_momentum_portfolio(market.close, lookback=20, top_n=3, scheme="equal").holdings
    small = execute_rebalance(targets, market, initial_cash=300_000.0, lot_size=100, slippage_fn=_slippage_factory(market))
    large = execute_rebalance(targets, market, initial_cash=3_000_000.0, lot_size=100, slippage_fn=_slippage_factory(market))

    small_path = ROOT / "artifacts" / "small.csv"
    large_path = ROOT / "artifacts" / "large.csv"
    compare_path = ROOT / "artifacts" / "slippage_compare.csv"
    save_csv(small.pnl, small_path)
    save_csv(large.pnl, large_path)

    compare = (
        small.pnl.assign(bucket="small")
        .groupby("bucket")[["slippage_cost", "turnover"]]
        .sum()
        .reset_index()
        .merge(
            large.pnl.assign(bucket="large").groupby("bucket")[["slippage_cost", "turnover"]].sum().reset_index(),
            how="outer",
        )
    )
    save_csv(compare, compare_path)

    small_cost = float(small.pnl["slippage_cost"].sum()) if not small.pnl.empty else 0.0
    large_cost = float(large.pnl["slippage_cost"].sum()) if not large.pnl.empty else 0.0
    steps = [
        "基于成交额和波动率建模动态滑点。",
        f"面板来源：{market.source_mode}。",
        "对比小额与大额资金场景下的滑点成本。",
        f"小额滑点 {small_cost:.2f}，大额滑点 {large_cost:.2f}。",
    ]
    artifacts = ["artifacts/small.csv", "artifacts/large.csv", "artifacts/slippage_compare.csv"]
    if small_cost > 0 and large_cost > small_cost:
        status = "pass"
        conclusion = "滑点随成交规模变化，大额交易成本显著高于小额交易。"
    else:
        status = "fail"
        conclusion = "滑点模型未体现规模差异或成本异常。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
