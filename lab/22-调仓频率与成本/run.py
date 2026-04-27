from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import (
    DEFAULT_UNIVERSE,
    ExperimentMeta,
    apply_costs,
    build_momentum_portfolio,
    execute_rebalance,
    load_market_panel,
    record_experiment,
    save_csv,
)


def _subsample_targets(targets: pd.DataFrame, step: int = 5) -> pd.DataFrame:
    dates = sorted(pd.to_datetime(targets["date"]).unique())
    keep = {date.strftime("%Y-%m-%d") for idx, date in enumerate(dates) if idx % step == 0}
    return targets[targets["date"].isin(keep)].reset_index(drop=True)


def main() -> None:
    meta = ExperimentMeta(
        code="22",
        title="调仓频率与成本",
        goal="验证较低调仓频率可压缩换手和交易成本。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    daily_targets = build_momentum_portfolio(market.close, lookback=20, top_n=3, scheme="equal").holdings
    weekly_targets = _subsample_targets(daily_targets, step=5)

    daily_exec = execute_rebalance(daily_targets, market, initial_cash=1_000_000.0, lot_size=100)
    weekly_exec = execute_rebalance(weekly_targets, market, initial_cash=1_000_000.0, lot_size=100)
    daily_costed = apply_costs(daily_exec.pnl, fee_bps=5, slippage_bps=1)
    weekly_costed = apply_costs(weekly_exec.pnl, fee_bps=5, slippage_bps=1)

    artifact_dir = ROOT / "artifacts"
    save_csv(daily_exec.pnl, artifact_dir / "daily_pnl.csv")
    save_csv(weekly_exec.pnl, artifact_dir / "weekly_pnl.csv")
    save_csv(daily_costed, artifact_dir / "daily_costed.csv")
    save_csv(weekly_costed, artifact_dir / "weekly_costed.csv")

    daily_turnover = float(daily_exec.pnl["turnover"].sum()) if not daily_exec.pnl.empty else 0.0
    weekly_turnover = float(weekly_exec.pnl["turnover"].sum()) if not weekly_exec.pnl.empty else 0.0
    daily_cost = float(daily_costed["cost"].sum()) if not daily_costed.empty else 0.0
    weekly_cost = float(weekly_costed["cost"].sum()) if not weekly_costed.empty else 0.0

    steps = [
        "对同一策略分别采用日频和周频子采样调仓。",
        "比较总换手和成本，检查频率下降后是否收敛。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = [
        "artifacts/daily_pnl.csv",
        "artifacts/weekly_pnl.csv",
        "artifacts/daily_costed.csv",
        "artifacts/weekly_costed.csv",
    ]
    if weekly_turnover <= daily_turnover and weekly_cost <= daily_cost:
        status = "pass"
        conclusion = "调仓频率下降后，换手和成本同步下降。"
    else:
        status = "fail"
        conclusion = "调仓频率与成本的关系未达到预期。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
