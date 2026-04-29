from __future__ import annotations

"""Deprecated compatibility layer for legacy allocation imports."""

from .allocators.base import AllocationResult
from .allocators.score import allocate_capital

__all__ = [
    "AllocationResult",
    "allocate_capital",
]
