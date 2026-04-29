"""Core signal layer."""

from .engine import SignalGenerator
from .factors import momentum_signal, sharpe_signal, trend_follow_signal
from .registry import SignalAdapter, build_signal_adapters, build_strategy_builder, build_strategy_spec, get_signal_adapter
from .specs import StrategySpec
from .validators import validate_strategy_output

__all__ = [
    "SignalGenerator",
    "SignalAdapter",
    "StrategySpec",
    "build_signal_adapters",
    "build_strategy_builder",
    "build_strategy_spec",
    "get_signal_adapter",
    "momentum_signal",
    "sharpe_signal",
    "trend_follow_signal",
    "validate_strategy_output",
]
