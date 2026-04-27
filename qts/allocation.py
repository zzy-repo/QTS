from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class AllocationResult:
    """描述策略层的资金分配结果。"""

    allocation: pd.DataFrame
    cash_left: float


def allocate_capital(strategy_signals: pd.DataFrame, total_cash: float, caps: dict[str, float] | None = None) -> AllocationResult:
    """按策略信号分配资金。"""
    if strategy_signals.empty:
        return AllocationResult(allocation=pd.DataFrame(columns=["strategy", "allocated_cash"]), cash_left=total_cash)
    grouped = strategy_signals.groupby("strategy")["score"].sum().abs()
    if grouped.sum() <= 0:
        weights = pd.Series(1.0 / len(grouped), index=grouped.index)
    else:
        weights = grouped / grouped.sum()
    if caps:
        weights = weights.clip(upper=pd.Series(caps))
        if weights.sum() > 0:
            weights = weights / weights.sum()
    allocation = pd.DataFrame({"strategy": weights.index, "allocated_cash": weights.values * float(total_cash)})
    return AllocationResult(allocation=allocation, cash_left=float(total_cash - allocation["allocated_cash"].sum()))
