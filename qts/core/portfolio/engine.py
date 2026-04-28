from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from ..data.models import ExecutionRun, MarketPanel
from ..signal.specs import StrategySpec
from .allocation import allocate_capital
from .results import StrategyRunResult, SystemRunResult, rolling_annualized_return


class _OptimizerLike(Protocol):
    mode: str

    def optimize(self, signals: pd.DataFrame) -> pd.DataFrame: ...


class _ExecutorLike(Protocol):
    mode: str

    def execute(
        self,
        target: pd.DataFrame,
        market: MarketPanel,
        *,
        initial_cash: float = 1_000_000.0,
        lot_size: int = 100,
    ) -> ExecutionRun: ...


@dataclass(frozen=True)
class PortfolioManager:
    """负责资金分配、组合执行和结果汇总。"""

    initial_cash: float = 1_000_000.0
    lot_size: int = 100
    capital_caps: dict[str, float] | None = None

    def build(
        self,
        *,
        strategies: list[StrategySpec],
        strategy_signals: pd.DataFrame,
        market: MarketPanel,
        optimizer: _OptimizerLike,
        executor: _ExecutorLike,
    ) -> SystemRunResult:
        """生成完整系统运行结果。"""
        allocation = allocate_capital(strategy_signals, total_cash=self.initial_cash, caps=self.capital_caps)
        alloc_map = allocation.allocation.set_index("strategy")["allocated_cash"].to_dict() if not allocation.allocation.empty else {}

        strategy_runs: list[StrategyRunResult] = []
        pnl_frames: list[pd.DataFrame] = []
        for spec in strategies:
            if "strategy" in strategy_signals.columns and not strategy_signals.empty:
                signals = strategy_signals[strategy_signals["strategy"] == spec.name].copy()
            else:
                signals = strategy_signals.iloc[0:0].copy()
            optimized = optimizer.optimize(signals)
            target = optimized[["date", "symbol", "weight"]] if not optimized.empty else pd.DataFrame(columns=["date", "symbol", "weight"])
            allocation_cash = float(alloc_map.get(spec.name, 0.0))
            execution = executor.execute(target, market, initial_cash=self.initial_cash, lot_size=self.lot_size)
            strategy_runs.append(
                StrategyRunResult(
                    name=spec.name,
                    signals=signals,
                    optimized=optimized,
                    execution=execution,
                    allocation_cash=allocation_cash,
                )
            )
            if not execution.pnl.empty:
                frame = execution.pnl[["date", "signal_date", "gross_return"]].copy()
                frame["strategy"] = spec.name
                frame["allocation_weight"] = allocation_cash / self.initial_cash if self.initial_cash else 0.0
                pnl_frames.append(frame)

        if pnl_frames:
            combined = pd.concat(pnl_frames, ignore_index=True)
            combined["weighted_return"] = combined["gross_return"] * combined["allocation_weight"]
            aggregate_pnl = combined.groupby("date", as_index=False).agg(
                gross_return=("weighted_return", "sum"),
                allocation_weight=("allocation_weight", "sum"),
                signal_date=("signal_date", "first"),
            )
            aggregate_pnl = aggregate_pnl.sort_values("date").reset_index(drop=True)
            equity = 1.0
            equity_rows: list[dict[str, object]] = []
            for _, row in aggregate_pnl.iterrows():
                equity *= 1.0 + float(row["gross_return"])
                equity_rows.append({"date": row["date"], "equity": equity * self.initial_cash})
            aggregate_equity = pd.DataFrame(equity_rows)
            aggregate_pnl["equity"] = aggregate_equity["equity"].values
            aggregate_pnl["cum_return"] = aggregate_pnl["equity"] / float(self.initial_cash) - 1.0
            aggregate_pnl["annualized_return"] = rolling_annualized_return(aggregate_pnl["cum_return"])
        else:
            aggregate_pnl = pd.DataFrame(
                columns=["date", "signal_date", "gross_return", "allocation_weight", "equity", "cum_return", "annualized_return"]
            )
            aggregate_equity = pd.DataFrame(columns=["date", "equity"])

        snapshot = {
            "strategy_names": [spec.name for spec in strategies],
            "optimizer_mode": optimizer.mode,
            "execution_mode": executor.mode,
            "initial_cash": self.initial_cash,
            "lot_size": self.lot_size,
            "allocation_rows": len(allocation.allocation),
        }
        return SystemRunResult(
            strategy_runs=strategy_runs,
            allocation=allocation,
            strategy_signals=strategy_signals,
            aggregate_pnl=aggregate_pnl,
            aggregate_equity=aggregate_equity,
            snapshot=snapshot,
        )
