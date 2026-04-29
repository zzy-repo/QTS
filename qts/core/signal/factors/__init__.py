"""Signal factor package."""

from .momentum import momentum_signal
from .sharpe import sharpe_signal
from .trend import trend_follow_signal

__all__ = [
    "momentum_signal",
    "sharpe_signal",
    "trend_follow_signal",
]
