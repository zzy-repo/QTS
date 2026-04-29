from __future__ import annotations

"""Deprecated compatibility layer for legacy allocation imports."""

from .allocators.base import AllocationContext, AllocationResult
from .allocators.score import allocate_capital

__all__ = [
    "AllocationContext",
    "AllocationResult",
    "allocate_capital",
]
