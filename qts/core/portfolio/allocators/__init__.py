"""Portfolio allocator package."""

from .base import AllocationResult
from .registry import AllocatorAdapter, build_allocators
from .score import score_allocate_capital

__all__ = [
    "AllocationResult",
    "AllocatorAdapter",
    "build_allocators",
    "score_allocate_capital",
]
