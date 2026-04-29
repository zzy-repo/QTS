from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .allocators import AllocationResult
from ..data.models import ExecutionRun

TRADING_DAYS_PER_YEAR = 252


def annualized_return(total_return: float, periods: int, trading_days_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    """计算年化收益。"""
    if periods <= 0:
        return float("nan")
    base = 1.0 + float(total_return)
    if base <= 0:
        return float("nan")
    return float(base ** (trading_days_per_year / float(periods)) - 1.0)


def rolling_annualized_return(
    cumulative_return: pd.Series,
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
) -> pd.Series:
    """按截至当日的累计收益，计算逐日年化收益。"""
    values = pd.to_numeric(cumulative_return, errors="coerce").to_numpy(dtype=float, copy=True)
    if values.size == 0:
        return pd.Series(dtype=float, index=cumulative_return.index, name="annualized_return")

    periods = np.arange(1, values.size + 1, dtype=float)
    base = 1.0 + values
    annualized = np.full(values.shape, np.nan, dtype=float)
    valid = np.isfinite(values) & (periods > 0.0) & (base > 0.0)
    annualized[valid] = np.power(base[valid], trading_days_per_year / periods[valid]) - 1.0
    return pd.Series(annualized, index=cumulative_return.index, name="annualized_return")


def final_annualized_return(frame: pd.DataFrame, trading_days_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    """提取结果表中最后一个有效年化收益；若缺失则按累计收益回算。"""
    if frame.empty:
        return float("nan")
    if "annualized_return" in frame.columns:
        annualized = pd.to_numeric(frame["annualized_return"], errors="coerce")
        if annualized.notna().any():
            return float(annualized.dropna().iloc[-1])
    if "cum_return" in frame.columns:
        cumulative = pd.to_numeric(frame["cum_return"], errors="coerce")
        valid = cumulative.dropna()
        if not valid.empty:
            return annualized_return(float(valid.iloc[-1]), len(valid), trading_days_per_year=trading_days_per_year)
    return float("nan")


def daily_pnl_view(frame: pd.DataFrame) -> pd.DataFrame:
    """把可能包含多 signal_date 的收益表压成按收益实现日唯一的一行。"""
    if frame.empty or "date" not in frame.columns:
        return frame.copy()
    daily = frame.copy()
    if "date" in daily.columns:
        daily["date"] = pd.to_datetime(daily["date"], format="mixed")
    aggregations: dict[str, str] = {}
    if "gross_return" in daily.columns:
        aggregations["gross_return"] = "sum"
    for column in ["equity", "cum_return", "annualized_return", "cash_weight", "cash_left"]:
        if column in daily.columns:
            aggregations[column] = "last"
    if "turnover" in daily.columns:
        aggregations["turnover"] = "sum"
    if "signal_date" in daily.columns:
        aggregations["signal_date"] = "last"
    if "allocation_weight" in daily.columns:
        aggregations["allocation_weight"] = "last"
    if not aggregations:
        return daily.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return daily.groupby("date", as_index=False).agg(aggregations).sort_values("date").reset_index(drop=True)


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
