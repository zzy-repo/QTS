"""Deprecated compatibility layer for legacy signal imports."""

from .factors import momentum_signal, sharpe_signal, trend_follow_signal
from .validators import validate_strategy_output

__all__ = [
    "momentum_signal",
    "sharpe_signal",
    "trend_follow_signal",
    "validate_strategy_output",
]
