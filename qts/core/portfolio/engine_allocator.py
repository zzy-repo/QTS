from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .allocators import AllocationContext, AllocationResult, build_allocators


@dataclass(frozen=True)
class Allocator:
    """把策略信号转换成策略级资金分配。"""

    mode: str = "score"

    def allocate(
        self,
        strategy_signals: pd.DataFrame,
        *,
        total_cash: float,
        caps: dict[str, float] | None = None,
        context: AllocationContext | None = None,
    ) -> AllocationResult:
        """执行选定的分配器。"""
        allocator = build_allocators().get(self.mode)
        if allocator is None:
            raise ValueError(f"未知的分配器模式：{self.mode}")
        return allocator.run(strategy_signals, total_cash, caps, context=context)
