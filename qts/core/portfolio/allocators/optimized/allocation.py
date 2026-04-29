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


def _portfolio_utility(weights: pd.Series, expected_returns: pd.Series, covariance: pd.DataFrame, *, risk_aversion: float) -> float:
    mu = expected_returns.reindex(weights.index).fillna(0.0).to_numpy(dtype=float)
    cov = covariance.reindex(index=weights.index, columns=weights.index).fillna(0.0).to_numpy(dtype=float)
    vector = weights.to_numpy(dtype=float)
    return float(mu @ vector) - risk_aversion * float(vector @ cov @ vector)


def _optimized_weights(expected_returns: pd.Series, covariance: pd.DataFrame, *, risk_aversion: float = 4.0) -> pd.Series:
    if covariance.empty:
        return pd.Series(dtype=float)
    names = list(covariance.index)
    mu = expected_returns.reindex(names).fillna(0.0)
    cov = covariance.reindex(index=names, columns=names).fillna(0.0)
    inv = np.linalg.pinv(cov.to_numpy(dtype=float))
    raw = pd.Series(np.clip(inv @ mu.to_numpy(dtype=float), 0.0, None), index=names, dtype=float)
    if float(raw.sum()) <= 0:
        raw = pd.Series(1.0 / len(names), index=names, dtype=float)
    min_var = pd.Series(np.clip(inv @ np.ones(len(names), dtype=float), 0.0, None), index=names, dtype=float)
    if float(min_var.sum()) <= 0:
        min_var = pd.Series(1.0 / len(names), index=names, dtype=float)

    candidates = [
        raw / float(raw.sum()),
        min_var / float(min_var.sum()),
        pd.Series(1.0 / len(names), index=names, dtype=float),
    ]
    best = candidates[-1]
    best_utility = float("-inf")
    for candidate in candidates:
        utility = _portfolio_utility(candidate, mu, cov, risk_aversion=risk_aversion)
        if utility > best_utility:
            best = candidate
            best_utility = utility
    return best


def optimized_allocate_capital(
    strategy_signals: pd.DataFrame,
    total_cash: float,
    caps: dict[str, float] | None = None,
    *,
    context: AllocationContext | None = None,
) -> AllocationResult:
    """优先基于历史策略收益估计 mu/Sigma，否则回退到信号代理版优化分配。"""
    stats = aggregate_strategy_statistics(strategy_signals)
    if stats.empty:
        return AllocationResult(allocation=pd.DataFrame(columns=["strategy", "allocated_cash"]), cash_left=float(total_cash))
    returns = strategy_return_history(strategy_signals, context)
    if not returns.empty and "date" in returns.columns:
        returns_only = returns.set_index("date").astype(float)
        covariance = regularize_covariance(returns_only)
        expected_returns = returns_only.mean()
        if float(expected_returns.abs().sum()) <= 0:
            weights = pd.Series(1.0 / len(expected_returns), index=expected_returns.index, dtype=float)
            return finalize_allocation(weights, total_cash, caps)
    else:
        score = stats.set_index("strategy")["score_strength"].astype(float)
        if float(score.sum()) <= 0:
            weights = pd.Series(1.0 / len(score), index=score.index, dtype=float)
            return finalize_allocation(weights, total_cash, caps)
        covariance = diagonal_covariance_from_volatility(stats)
        expected_returns = score / float(score.sum())
    weights = _optimized_weights(expected_returns, covariance, risk_aversion=4.0)
    return finalize_allocation(weights, total_cash, caps)
