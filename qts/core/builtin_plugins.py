from __future__ import annotations

import pandas as pd

from .plugins import hookimpl


class BuiltinQTSPlugin:
    """内置插件，提供默认的核心实现集合。"""

    @hookimpl
    def qts_register_factors(self):
        from .factor.base import FactorAdapter
        from .factor.factors import momentum_signal, sharpe_signal, trend_follow_signal

        return [
            FactorAdapter(name="momentum", run=momentum_signal),
            FactorAdapter(name="trend", run=trend_follow_signal),
            FactorAdapter(name="sharpe", run=sharpe_signal),
        ]

    @hookimpl
    def qts_register_strategies(self):
        from .strategy.base import StrategyAdapter
        from .strategy.strategies import build_factor_strategy

        return [
            StrategyAdapter(name="factor", build=build_factor_strategy),
        ]

    @hookimpl
    def qts_register_optimizers(self, capped_cap: float):
        from .optimize.optimizers.base import OptimizerAdapter
        from .optimize.optimizers.blend import blend_weight_optimizer
        from .optimize.optimizers.capped import capped_optimizer
        from .optimize.optimizers.equal import equal_weight_optimizer
        from .optimize.optimizers.inv_vol import inverse_vol_optimizer
        from .optimize.optimizers.score import score_weight_optimizer

        def capped_run(signals: pd.DataFrame) -> pd.DataFrame:
            return capped_optimizer(signals, cap=capped_cap)

        def blend_run(signals: pd.DataFrame) -> pd.DataFrame:
            return blend_weight_optimizer(signals, score_weight=0.5)

        return [
            OptimizerAdapter(name="equal", run=equal_weight_optimizer),
            OptimizerAdapter(name="score", run=score_weight_optimizer),
            OptimizerAdapter(name="inv_vol", run=inverse_vol_optimizer),
            OptimizerAdapter(name="blend", run=blend_run),
            OptimizerAdapter(name="capped", run=capped_run),
        ]

    @hookimpl
    def qts_register_allocators(self):
        from .portfolio.allocators.base import AllocatorAdapter
        from .portfolio.allocators.equal import equal_allocate_capital
        from .portfolio.allocators.optimized import optimized_allocate_capital
        from .portfolio.allocators.risk_parity import risk_parity_allocate_capital
        from .portfolio.allocators.score import score_allocate_capital

        return [
            AllocatorAdapter(name="score", run=score_allocate_capital),
            AllocatorAdapter(name="equal", run=equal_allocate_capital),
            AllocatorAdapter(name="risk_parity", run=risk_parity_allocate_capital),
            AllocatorAdapter(name="optimized", run=optimized_allocate_capital),
        ]
