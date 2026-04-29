"""Deprecated compatibility layer for legacy allocation imports."""

from __future__ import annotations

from .allocators.base import AllocationContext, AllocationResult
from .allocators.score.allocation import allocate_capital

__all__ = [
    "AllocationContext",
    "AllocationResult",
    "allocate_capital",
]
