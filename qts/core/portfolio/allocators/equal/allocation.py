from __future__ import annotations

import pandas as pd

from ..base import AllocationContext, AllocationResult
from ..common import aggregate_strategy_statistics, finalize_allocation


def equal_allocate_capital(
    strategy_signals: pd.DataFrame,
    total_cash: float,
    caps: dict[str, float] | None = None,
    *,
    context: AllocationContext | None = None,
) -> AllocationResult:
    """按策略数量等权分配资金。"""
    stats = aggregate_strategy_statistics(strategy_signals)
    if stats.empty:
        return AllocationResult(allocation=pd.DataFrame(columns=["strategy", "allocated_cash"]), cash_left=float(total_cash))
    weights = pd.Series(1.0 / len(stats), index=stats["strategy"], dtype=float)
    return finalize_allocation(weights, total_cash, caps)
