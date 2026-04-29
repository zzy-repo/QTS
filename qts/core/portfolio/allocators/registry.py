from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .base import AllocationResult
from .equal import equal_allocate_capital
from .optimized import optimized_allocate_capital
from .risk_parity import risk_parity_allocate_capital
from .score import score_allocate_capital


@dataclass(frozen=True)
class AllocatorAdapter:
    """描述一个资金分配器实现。"""

    name: str
    run: Callable[..., AllocationResult]


def build_allocators() -> dict[str, AllocatorAdapter]:
    """构建可用资金分配器集合。"""
    return {
        "score": AllocatorAdapter(name="score", run=score_allocate_capital),
        "equal": AllocatorAdapter(name="equal", run=equal_allocate_capital),
        "risk_parity": AllocatorAdapter(name="risk_parity", run=risk_parity_allocate_capital),
        "optimized": AllocatorAdapter(name="optimized", run=optimized_allocate_capital),
    }


def get_allocator(mode: str) -> AllocatorAdapter:
    """按名称获取单个分配器实现。"""
    allocator = build_allocators().get(mode)
    if allocator is None:
        raise ValueError(f"未知的分配器模式：{mode}")
    return allocator
