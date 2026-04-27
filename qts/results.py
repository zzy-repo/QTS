from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .allocation import AllocationResult
from .execution import ExecutionRun

TRADING_DAYS_PER_YEAR = 252


def annualized_return(total_return: float, periods: int, trading_days_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    """计算年化收益。"""
    if periods <= 0:
        return float("nan")
    base = 1.0 + float(total_return)
    if base <= 0:
        return float("nan")
    return float(base ** (trading_days_per_year / float(periods)) - 1.0)


@dataclass(frozen=True)
class StrategyRunResult:
    """保存单个策略运行后的结果。"""

    name: str
    signals: pd.DataFrame
    optimized: pd.DataFrame
    execution: ExecutionRun
    allocation_cash: float


@dataclass(frozen=True)
class SystemRunResult:
    """保存完整系统运行后的结果。"""

    strategy_runs: list[StrategyRunResult]
    allocation: AllocationResult
    strategy_signals: pd.DataFrame
    aggregate_pnl: pd.DataFrame
    aggregate_equity: pd.DataFrame
    snapshot: dict[str, object] = field(default_factory=dict)
