from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .base import AllocationResult
from .score import score_allocate_capital


@dataclass(frozen=True)
class AllocatorAdapter:
    """描述一个资金分配器实现。"""

    name: str
    run: Callable[[pd.DataFrame, float, dict[str, float] | None], AllocationResult]


def build_allocators() -> dict[str, AllocatorAdapter]:
    """构建可用资金分配器集合。"""
    return {
        "score": AllocatorAdapter(name="score", run=score_allocate_capital),
    }
