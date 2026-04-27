from __future__ import annotations

from dataclasses import dataclass, field

from .models import MarketPanel
from .pipeline import Executor, Optimizer, PortfolioManager, SignalGenerator, SystemPipeline
from .results import SystemRunResult
from .specs import StrategySpec


@dataclass
class MultiDecisionSystem:
    """系统级门面，负责装配并运行管线。"""

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
    _pipeline: SystemPipeline | None = field(default=None, init=False, repr=False)

    def build_pipeline(self) -> SystemPipeline:
        """构建当前系统配置对应的流水线。"""
        return SystemPipeline(
            signal_generator=SignalGenerator(strategies=self.strategies),
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
            raise ValueError("at least one strategy is required")
        return self.pipeline.run(market)
