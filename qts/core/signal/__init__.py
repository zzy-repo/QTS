"""Core signal layer."""

from .engine import SignalGenerator
from .factors import momentum_signal, sharpe_signal, trend_follow_signal
from .specs import StrategySpec
from .validators import validate_strategy_output

__all__ = [
    "SignalGenerator",
    "StrategySpec",
    "momentum_signal",
    "sharpe_signal",
    "trend_follow_signal",
    "validate_strategy_output",
]
