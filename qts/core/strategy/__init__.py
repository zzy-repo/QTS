"""Core strategy layer."""

from .engine import SignalGenerator
from .registry import StrategyAdapter, build_strategy_adapters, build_strategy_builder, build_strategy_spec, get_strategy_adapter
from .specs import StrategySpec
from .validators import validate_strategy_output

__all__ = [
    "SignalGenerator",
    "StrategyAdapter",
    "StrategySpec",
    "build_strategy_adapters",
    "build_strategy_builder",
    "build_strategy_spec",
    "get_strategy_adapter",
    "validate_strategy_output",
]
