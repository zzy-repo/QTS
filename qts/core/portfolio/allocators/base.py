from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ...data.models import MarketPanel


@dataclass(frozen=True)
class AllocationContext:
    """描述分配器可选使用的额外风险估计上下文。"""

    market: MarketPanel | None = None
    strategy_return_history: pd.DataFrame | None = None


@dataclass(frozen=True)
class AllocationResult:
    """描述策略层的资金分配结果。"""

    allocation: pd.DataFrame
    cash_left: float
