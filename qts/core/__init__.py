"""Core layer package."""

from .analysis import (
    cap_proxy_benchmark,
    compute_performance_metrics,
    compute_rolling_metrics,
    compute_tail_metrics,
    equal_weight_benchmark,
    historical_completeness,
    performance_summary_from_pnl,
    risk_state_machine,
    selection_stability,
)
from .factor import FactorAdapter, build_factor_adapters, get_factor_adapter
from .strategy import SignalGenerator, StrategyAdapter, StrategySpec, build_strategy_adapters, build_strategy_builder, build_strategy_spec, get_strategy_adapter
from .strategy import validate_strategy_output

__all__ = [
    "FactorAdapter",
    "SignalGenerator",
    "StrategyAdapter",
    "StrategySpec",
    "build_factor_adapters",
    "cap_proxy_benchmark",
    "compute_performance_metrics",
    "compute_rolling_metrics",
    "compute_tail_metrics",
    "build_strategy_adapters",
    "build_strategy_builder",
    "build_strategy_spec",
    "equal_weight_benchmark",
    "get_factor_adapter",
    "get_strategy_adapter",
    "historical_completeness",
    "performance_summary_from_pnl",
    "risk_state_machine",
    "selection_stability",
    "validate_strategy_output",
]
