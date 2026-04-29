"""Portfolio allocator package."""

from .base import AllocationContext, AllocationResult, AllocatorAdapter
from .equal import equal_allocate_capital
from .optimized import optimized_allocate_capital
from .risk_parity import risk_parity_allocate_capital
from .score import score_allocate_capital
from ...plugins import collect_allocator_adapters


def build_allocators() -> dict[str, AllocatorAdapter]:
    """通过插件系统收集可用资金分配器。"""
    return collect_allocator_adapters()


def get_allocator(mode: str) -> AllocatorAdapter:
    """按名称获取单个分配器实现。"""
    allocator = build_allocators().get(mode)
    if allocator is None:
        raise ValueError(f"未知的分配器模式：{mode}")
    return allocator

__all__ = [
    "AllocationResult",
    "AllocationContext",
    "AllocatorAdapter",
    "build_allocators",
    "get_allocator",
    "equal_allocate_capital",
    "optimized_allocate_capital",
    "risk_parity_allocate_capital",
    "score_allocate_capital",
]
