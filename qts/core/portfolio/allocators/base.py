from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class AllocationResult:
    """描述策略层的资金分配结果。"""

    allocation: pd.DataFrame
    cash_left: float
