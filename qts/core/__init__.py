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
from .plugins import (
    activate_plugin_runtime,
    build_plugin_runtime,
    get_plugin_manager,
    hookimpl,
    plugin_context,
    register_plugin,
    unregister_plugin,
)
from .strategy import SignalGenerator, StrategyAdapter, StrategySpec, build_strategy_adapters, build_strategy_builder, build_strategy_spec, get_strategy_adapter
from .strategy import validate_strategy_output

__all__ = [
    "FactorAdapter",
    "SignalGenerator",
    "StrategyAdapter",
    "StrategySpec",
    "activate_plugin_runtime",
    "build_plugin_runtime",
    "build_factor_adapters",
    "cap_proxy_benchmark",
    "compute_performance_metrics",
    "compute_rolling_metrics",
    "compute_tail_metrics",
    "build_strategy_adapters",
    "build_strategy_builder",
    "build_strategy_spec",
    "equal_weight_benchmark",
    "get_plugin_manager",
    "get_factor_adapter",
    "get_strategy_adapter",
    "historical_completeness",
    "hookimpl",
    "performance_summary_from_pnl",
    "plugin_context",
    "register_plugin",
    "risk_state_machine",
    "selection_stability",
    "unregister_plugin",
    "validate_strategy_output",
]
