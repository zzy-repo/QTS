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


def _strategy_signals_for(strategy_signals: pd.DataFrame, strategy_name: str) -> pd.DataFrame:
    """提取单个策略对应的信号明细。"""
    if "strategy" in strategy_signals.columns and not strategy_signals.empty:
        return strategy_signals[strategy_signals["strategy"] == strategy_name].copy()
    return strategy_signals.iloc[0:0].copy()


def _strategy_target(optimized: pd.DataFrame) -> pd.DataFrame:
    """把优化结果整理成执行器输入。"""
    if optimized.empty:
        return pd.DataFrame(columns=["date", "symbol", "weight"])
    return optimized[["date", "symbol", "weight"]]


def _execution_pnl_frame(execution: ExecutionRun, strategy_name: str, allocation_cash: float, initial_cash: float) -> pd.DataFrame | None:
    """把单策略执行结果整理成可聚合的收益表。"""
    if execution.pnl.empty:
        return None
    frame = execution.pnl[["date", "signal_date", "gross_return"]].copy()
    frame["strategy"] = strategy_name
    frame["allocation_weight"] = allocation_cash / initial_cash if initial_cash else 0.0
    return frame


def _aggregate_portfolio_frames(pnl_frames: list[pd.DataFrame], initial_cash: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """聚合各策略收益并生成组合权益曲线。"""
    if not pnl_frames:
        aggregate_pnl = pd.DataFrame(
            columns=["date", "signal_date", "gross_return", "allocation_weight", "equity", "cum_return", "annualized_return"]
        )
        aggregate_equity = pd.DataFrame(columns=["date", "equity"])
        return aggregate_pnl, aggregate_equity

    combined = pd.concat(pnl_frames, ignore_index=True)
    combined["weighted_return"] = combined["gross_return"] * combined["allocation_weight"]
    aggregate_pnl = combined.groupby("date", as_index=False).agg(
        gross_return=("weighted_return", "sum"),
        allocation_weight=("allocation_weight", "sum"),
        signal_date=("signal_date", "first"),
    )
    aggregate_pnl = aggregate_pnl.sort_values("date").reset_index(drop=True)

    equity_value = 1.0
    equity_rows: list[dict[str, object]] = []
    for _, row in aggregate_pnl.iterrows():
        equity_value *= 1.0 + float(row["gross_return"])
        equity_rows.append({"date": row["date"], "equity": equity_value * initial_cash})
    aggregate_equity = pd.DataFrame(equity_rows)
    aggregate_pnl["equity"] = aggregate_equity["equity"].values
    aggregate_pnl["cum_return"] = aggregate_pnl["equity"] / float(initial_cash) - 1.0
    aggregate_pnl["annualized_return"] = rolling_annualized_return(aggregate_pnl["cum_return"])
    return aggregate_pnl, aggregate_equity


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
            signals = _strategy_signals_for(strategy_signals, spec.name)
            optimized = optimizer.optimize(signals)
            target = _strategy_target(optimized)
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
            pnl_frame = _execution_pnl_frame(execution, spec.name, allocation_cash, self.initial_cash)
            if pnl_frame is not None:
                pnl_frames.append(pnl_frame)

        aggregate_pnl, aggregate_equity = _aggregate_portfolio_frames(pnl_frames, self.initial_cash)

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
