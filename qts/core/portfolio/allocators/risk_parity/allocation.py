from __future__ import annotations

import numpy as np
import pandas as pd

from ..base import AllocationContext, AllocationResult
from ..common import (
    aggregate_strategy_statistics,
    diagonal_covariance_from_volatility,
    finalize_allocation,
    regularize_covariance,
    strategy_return_history,
)


def _risk_parity_weights(covariance: pd.DataFrame, *, max_iter: int = 2000, tol: float = 1e-6) -> pd.Series:
    if covariance.empty:
        return pd.Series(dtype=float)
    names = list(covariance.index)
    cov = covariance.reindex(index=names, columns=names).fillna(0.0).to_numpy(dtype=float)
    weights = np.full(len(names), 1.0 / len(names), dtype=float)
    target = 1.0 / len(names)
    for _ in range(max_iter):
        marginal = cov @ weights
        contributions = weights * marginal
        total = float(contributions.sum())
        if total <= 0 or not np.isfinite(total):
            break
        normalized = contributions / total
        if float(np.max(np.abs(normalized - target))) <= tol:
            break
        updated = weights * target / np.maximum(normalized, 1e-12)
        updated = np.clip(updated, 1e-12, None)
        updated = updated / updated.sum()
        if float(np.linalg.norm(updated - weights, ord=1)) <= tol:
            weights = updated
            break
        weights = 0.5 * weights + 0.5 * updated
        weights = weights / weights.sum()
    return pd.Series(weights, index=names, dtype=float)


def risk_parity_allocate_capital(
    strategy_signals: pd.DataFrame,
    total_cash: float,
    caps: dict[str, float] | None = None,
    *,
    context: AllocationContext | None = None,
) -> AllocationResult:
    """优先基于历史策略收益协方差，否则回退到波动率代理版风险平价。"""
    stats = aggregate_strategy_statistics(strategy_signals)
    if stats.empty:
        return AllocationResult(allocation=pd.DataFrame(columns=["strategy", "allocated_cash"]), cash_left=float(total_cash))
    returns = strategy_return_history(strategy_signals, context)
    if not returns.empty and "date" in returns.columns:
        covariance = regularize_covariance(returns.set_index("date").astype(float))
    else:
        covariance = diagonal_covariance_from_volatility(stats)
    weights = _risk_parity_weights(covariance)
    return finalize_allocation(weights, total_cash, caps)
