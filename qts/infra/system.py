from __future__ import annotations

from dataclasses import dataclass, field, replace

import pandas as pd

from ..core.analysis import equal_weight_benchmark, performance_summary_from_pnl, risk_state_machine
from ..core.data.models import MarketPanel
from ..core.execution.engine import Executor
from ..core.optimize.engine import Optimizer
from ..core.portfolio.engine_allocator import Allocator
from ..core.portfolio.engine import PortfolioManager
from ..core.portfolio.results import SystemRunResult, daily_pnl_view
from ..core.signal.engine import SignalGenerator
from ..core.signal.specs import StrategySpec


@dataclass
class SystemPipeline:
    """编排信号、优化、执行和组合管理。"""

    signal_generator: SignalGenerator
    allocator: Allocator
    optimizer: Optimizer
    executor: Executor
    portfolio_manager: PortfolioManager

    def run(self, market: MarketPanel) -> SystemRunResult:
        """运行完整处理流水线。"""
        strategy_signals = self.signal_generator.generate(market)
        result = self.portfolio_manager.build(
            strategies=self.signal_generator.strategies,
            strategy_signals=strategy_signals,
            market=market,
            allocator=self.allocator,
            optimizer=self.optimizer,
            executor=self.executor,
        )
        benchmark = equal_weight_benchmark(market.close) if not market.close.empty else None
        performance = performance_summary_from_pnl(daily_pnl_view(result.aggregate_pnl), benchmark=benchmark)
        snapshot = dict(result.snapshot)
        if not performance.empty:
            snapshot["performance"] = performance.iloc[0].to_dict()
        return replace(result, snapshot=snapshot)


@dataclass
class MultiDecisionSystem:
    """系统级门面，负责装配并运行管线。"""

    strategies: list[StrategySpec]
    allocation_mode: str = "score"
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
    _pipeline: SystemPipeline | None = field(default=None, init=False, repr=False)

    def build_pipeline(self) -> SystemPipeline:
        """构建当前系统配置对应的流水线。"""
        return SystemPipeline(
            signal_generator=SignalGenerator(strategies=self.strategies),
            allocator=Allocator(mode=self.allocation_mode),
            optimizer=Optimizer(mode=self.optimizer_mode, capped_cap=self.optimizer_cap),
            executor=Executor(
                mode=self.execution_mode,
                slippage_base_bps=self.slippage_base_bps,
                participation_scale=self.slippage_participation_scale,
                vol_scale=self.slippage_vol_scale,
                max_adv_pct=self.max_adv_pct,
            ),
            portfolio_manager=PortfolioManager(
                initial_cash=self.initial_cash,
                lot_size=self.lot_size,
                capital_caps=self.capital_caps,
            ),
        )

    @property
    def pipeline(self) -> SystemPipeline:
        """懒加载系统流水线。"""
        if self._pipeline is None:
            self._pipeline = self.build_pipeline()
        return self._pipeline

    def run(self, market: MarketPanel) -> SystemRunResult:
        """运行完整多策略系统。"""
        if not self.strategies:
            raise ValueError("至少需要配置一个策略")
        result = self.pipeline.run(market)
        risk_frame = risk_state_machine(
            result.aggregate_equity["equity"] if not result.aggregate_equity.empty else pd.Series(dtype=float)
        )
        snapshot = dict(result.snapshot)
        snapshot["risk_state_rows"] = len(risk_frame)
        return replace(result, snapshot=snapshot)
