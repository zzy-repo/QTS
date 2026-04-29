from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .allocators import AllocationContext, AllocationResult, AllocatorAdapter, get_allocator


@dataclass(frozen=True)
class Allocator:
    """把策略信号转换成策略级资金分配。"""

    mode: str = "score"
    _adapter: AllocatorAdapter = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_adapter", get_allocator(self.mode))

    def allocate(
        self,
        strategy_signals: pd.DataFrame,
        *,
        total_cash: float,
        caps: dict[str, float] | None = None,
        context: AllocationContext | None = None,
    ) -> AllocationResult:
        """执行选定的分配器。"""
        return self._adapter.run(strategy_signals, total_cash, caps, context=context)
