from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .allocation import allocate_capital
from .diagnostics import risk_state_machine
from .execution import ExecutionRun
from .models import MarketPanel, StrategyInput
from .optimization import build_optimizers
from .resilience import build_execution_adapters
from .results import StrategyRunResult, SystemRunResult, annualized_return
from .specs import StrategySpec


@dataclass(frozen=True)
class SignalGenerator:
    """生成策略信号。"""

    strategies: list[StrategySpec]

    def generate(self, market: MarketPanel) -> pd.DataFrame:
        """把市场数据转换为统一信号表。"""
        frames: list[pd.DataFrame] = []
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
            frames.append(signals)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


@dataclass(frozen=True)
class Optimizer:
    """把信号转换成目标权重。"""

    mode: str = "score"
    capped_cap: float = 0.4

    def optimize(self, signals: pd.DataFrame) -> pd.DataFrame:
        """执行选定的优化器。"""
        optimizer = build_optimizers(capped_cap=self.capped_cap).get(self.mode)
        if optimizer is None:
            raise ValueError(f"unknown optimizer mode: {self.mode}")
        return optimizer.run(signals)


@dataclass(frozen=True)
class Executor:
    """把目标权重执行成成交结果。"""

    mode: str = "backtest"
    slippage_base_bps: float = 1.0
    participation_scale: float = 0.035
    vol_scale: float = 0.15
    max_adv_pct: float = 0.02

    def execute(
        self,
        target: pd.DataFrame,
        market: MarketPanel,
        *,
        initial_cash: float = 1_000_000.0,
        lot_size: int = 100,
    ) -> ExecutionRun:
        """执行目标组合。"""
        adapter = build_execution_adapters(
            slippage_base_bps=self.slippage_base_bps,
            participation_scale=self.participation_scale,
            vol_scale=self.vol_scale,
            max_adv_pct=self.max_adv_pct,
        ).get(self.mode)
        if adapter is None:
            raise ValueError(f"unknown execution mode: {self.mode}")
        return adapter.run(target, market, initial_cash=initial_cash, lot_size=lot_size)


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
        optimizer: Optimizer,
        executor: Executor,
    ) -> SystemRunResult:
        """生成完整系统运行结果。"""
        allocation = allocate_capital(strategy_signals, total_cash=self.initial_cash, caps=self.capital_caps)
        alloc_map = allocation.allocation.set_index("strategy")["allocated_cash"].to_dict() if not allocation.allocation.empty else {}

        strategy_runs: list[StrategyRunResult] = []
        pnl_frames: list[pd.DataFrame] = []
        for spec in strategies:
            signals = strategy_signals[strategy_signals["strategy"] == spec.name].copy()
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
            "strategy_names": [spec.name for spec in strategies],
            "optimizer_mode": optimizer.mode,
            "execution_mode": executor.mode,
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


@dataclass(frozen=True)
class SystemPipeline:
    """编排信号、优化、执行和组合管理。"""

    signal_generator: SignalGenerator
    optimizer: Optimizer
    executor: Executor
    portfolio_manager: PortfolioManager

    def run(self, market: MarketPanel) -> SystemRunResult:
        """运行完整处理流水线。"""
        strategy_signals = self.signal_generator.generate(market)
        return self.portfolio_manager.build(
            strategies=self.signal_generator.strategies,
            strategy_signals=strategy_signals,
            market=market,
            optimizer=self.optimizer,
            executor=self.executor,
        )
