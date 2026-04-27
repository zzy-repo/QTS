from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from .allocation import AllocationResult, allocate_capital
from .diagnostics import risk_state_machine
from .models import ExecutionRun, MarketPanel, StrategyInput
from .optimization import build_optimizers
from .resilience import build_execution_adapters

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class StrategySpec:
    name: str
    builder: Callable[[StrategyInput], pd.DataFrame]
    lookback: int = 20
    top_n: int = 3


@dataclass(frozen=True)
class StrategyRunResult:
    name: str
    signals: pd.DataFrame
    optimized: pd.DataFrame
    execution: ExecutionRun
    allocation_cash: float


@dataclass(frozen=True)
class SystemRunResult:
    strategy_runs: list[StrategyRunResult]
    allocation: AllocationResult
    strategy_signals: pd.DataFrame
    aggregate_pnl: pd.DataFrame
    aggregate_equity: pd.DataFrame
    snapshot: dict[str, object] = field(default_factory=dict)


def annualized_return(total_return: float, periods: int, trading_days_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    if periods <= 0:
        return float("nan")
    base = 1.0 + float(total_return)
    if base <= 0:
        return float("nan")
    return float(base ** (trading_days_per_year / float(periods)) - 1.0)


@dataclass
class MultiDecisionSystem:
    strategies: list[StrategySpec]
    optimizer_mode: str = "score"
    execution_mode: str = "backtest"
    initial_cash: float = 1_000_000.0
    lot_size: int = 100
    capital_caps: dict[str, float] | None = None
    optimizer_cap: float = 0.4
    max_adv_pct: float = 0.02
    slippage_base_bps: float = 1.0
    slippage_participation_scale: float = 0.035
    slippage_vol_scale: float = 0.15

    def run(self, market: MarketPanel) -> SystemRunResult:
        if not self.strategies:
            raise ValueError("at least one strategy is required")

        strategy_frames: list[pd.DataFrame] = []
        for spec in self.strategies:
            data = StrategyInput(
                close=market.close,
                volume=market.volume,
                amount=market.amount,
                lookback=spec.lookback,
                top_n=spec.top_n,
            )
            signals = spec.builder(data).copy()
            if signals.empty:
                continue
            signals["strategy"] = spec.name
            strategy_frames.append(signals)

        strategy_signals = pd.concat(strategy_frames, ignore_index=True) if strategy_frames else pd.DataFrame()
        allocation = allocate_capital(strategy_signals, total_cash=self.initial_cash, caps=self.capital_caps)
        alloc_map = allocation.allocation.set_index("strategy")["allocated_cash"].to_dict() if not allocation.allocation.empty else {}

        optimizers = build_optimizers(capped_cap=self.optimizer_cap)
        adapters = build_execution_adapters(
            slippage_base_bps=self.slippage_base_bps,
            participation_scale=self.slippage_participation_scale,
            vol_scale=self.slippage_vol_scale,
            max_adv_pct=self.max_adv_pct,
        )
        optimizer = optimizers.get(self.optimizer_mode)
        if optimizer is None:
            raise ValueError(f"unknown optimizer mode: {self.optimizer_mode}")
        executor = adapters.get(self.execution_mode)
        if executor is None:
            raise ValueError(f"unknown execution mode: {self.execution_mode}")

        strategy_runs: list[StrategyRunResult] = []
        pnl_frames: list[pd.DataFrame] = []
        for spec in self.strategies:
            signals = strategy_signals[strategy_signals["strategy"] == spec.name].copy()
            optimized = optimizer.run(signals)
            target = optimized[["date", "symbol", "weight"]] if not optimized.empty else pd.DataFrame(columns=["date", "symbol", "weight"])
            allocation_cash = float(alloc_map.get(spec.name, 0.0))
            execution = executor.run(target, market, initial_cash=self.initial_cash, lot_size=self.lot_size)
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
                frame = execution.pnl[["date", "gross_return"]].copy()
                frame["strategy"] = spec.name
                frame["allocation_weight"] = allocation_cash / self.initial_cash if self.initial_cash else 0.0
                pnl_frames.append(frame)

        if pnl_frames:
            combined = pd.concat(pnl_frames, ignore_index=True)
            combined["weighted_return"] = combined["gross_return"] * combined["allocation_weight"]
            aggregate_pnl = combined.groupby("date", as_index=False).agg(
                gross_return=("weighted_return", "sum"),
                allocation_weight=("allocation_weight", "sum"),
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
            aggregate_pnl["annualized_return"] = annualized_return(
                float(aggregate_pnl["cum_return"].iloc[-1]),
                len(aggregate_pnl),
            )
        else:
            aggregate_pnl = pd.DataFrame(
                columns=["date", "gross_return", "allocation_weight", "equity", "cum_return", "annualized_return"]
            )
            aggregate_equity = pd.DataFrame(columns=["date", "equity"])

        risk_frame = risk_state_machine(aggregate_equity["equity"] if not aggregate_equity.empty else pd.Series(dtype=float))
        snapshot = {
            "strategy_names": [spec.name for spec in self.strategies],
            "optimizer_mode": self.optimizer_mode,
            "execution_mode": self.execution_mode,
            "initial_cash": self.initial_cash,
            "lot_size": self.lot_size,
            "allocation_rows": len(allocation.allocation),
            "risk_state_rows": len(risk_frame),
        }
        return SystemRunResult(
            strategy_runs=strategy_runs,
            allocation=allocation,
            strategy_signals=strategy_signals,
            aggregate_pnl=aggregate_pnl,
            aggregate_equity=aggregate_equity,
            snapshot=snapshot,
        )


def summarize_system_run(result: SystemRunResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    final_equity = float(result.aggregate_equity["equity"].iloc[-1]) if not result.aggregate_equity.empty else 0.0
    aggregate_total_return = float(result.aggregate_pnl["cum_return"].iloc[-1]) if not result.aggregate_pnl.empty else 0.0
    aggregate_annualized_return = annualized_return(aggregate_total_return, len(result.aggregate_pnl))
    for run in result.strategy_runs:
        pnl = run.execution.pnl
        total_return = float(pnl["cum_return"].iloc[-1]) if not pnl.empty and "cum_return" in pnl.columns else 0.0
        rows.append(
            {
                "strategy": run.name,
                "allocation_cash": run.allocation_cash,
                "signal_rows": len(run.signals),
                "pnl_rows": len(pnl),
                "final_equity": float(pnl["equity"].iloc[-1]) if not pnl.empty else 0.0,
                "annualized_return": annualized_return(total_return, len(pnl)),
            }
        )
    rows.append(
        {
            "strategy": "aggregate",
            "allocation_cash": result.allocation.allocation["allocated_cash"].sum() if not result.allocation.allocation.empty else 0.0,
            "signal_rows": len(result.strategy_signals),
            "pnl_rows": len(result.aggregate_pnl),
            "final_equity": final_equity,
            "annualized_return": aggregate_annualized_return,
        }
    )
    return pd.DataFrame(rows)
