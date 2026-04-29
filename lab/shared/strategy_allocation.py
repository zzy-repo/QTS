from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .allocation import AllocationResult
from .backtest import MarketPanel


@dataclass(frozen=True)
class StrategyAllocationStudy:
    signals: pd.DataFrame
    strategy_returns: pd.DataFrame
    covariance: pd.DataFrame
    expected_returns: pd.Series


def _serialize_date(value: object) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def build_strategy_allocation_study(
    market: MarketPanel,
    *,
    lookback: int = 20,
    top_n: int = 3,
    history_window: int = 40,
) -> StrategyAllocationStudy:
    close = market.close.copy()
    asset_returns = close.pct_change()
    next_day_returns = asset_returns.shift(-1)

    momentum_score = close.pct_change(lookback)
    trend_score = 0.5 * close.pct_change(max(2, lookback // 2)) + 0.5 * close.pct_change(lookback)
    defensive_score = -asset_returns.rolling(max(5, lookback // 2), min_periods=max(5, lookback // 2)).std(ddof=0)
    strategy_score_frames = {
        "momentum": momentum_score,
        "trend": trend_score,
        "defensive": defensive_score,
    }

    signal_rows: list[dict[str, object]] = []
    return_rows: list[dict[str, object]] = []
    start = max(lookback, history_window)
    for date in close.index[start:-1]:
        return_row: dict[str, object] = {"date": _serialize_date(date)}
        for strategy, score_frame in strategy_score_frames.items():
            selected = score_frame.loc[date].dropna().sort_values(ascending=False).head(top_n)
            if selected.empty:
                continue
            symbol_weights = pd.Series(1.0 / len(selected), index=selected.index, dtype=float)
            realized = next_day_returns.loc[date].reindex(selected.index).fillna(0.0)
            return_row[strategy] = float((symbol_weights * realized).sum())
            for rank, (symbol, score) in enumerate(selected.items(), start=1):
                signal_rows.append(
                    {
                        "date": _serialize_date(date),
                        "strategy": strategy,
                        "symbol": symbol,
                        "rank": rank,
                        "score": float(score),
                        "weight": float(symbol_weights.loc[symbol]),
                    }
                )
        if len(return_row) > 1:
            return_rows.append(return_row)

    signals = pd.DataFrame(signal_rows)
    strategy_returns = pd.DataFrame(return_rows)
    if strategy_returns.empty:
        strategy_returns = pd.DataFrame(columns=["date", "momentum", "trend", "defensive"])
        covariance = pd.DataFrame()
        expected_returns = pd.Series(dtype=float)
    else:
        strategy_returns["date"] = pd.to_datetime(strategy_returns["date"])
        strategy_returns = strategy_returns.sort_values("date").reset_index(drop=True)
        returns_only = strategy_returns.set_index("date").astype(float)
        covariance = _regularize_covariance(returns_only.tail(history_window))
        expected_returns = returns_only.tail(history_window).mean()
    return StrategyAllocationStudy(
        signals=signals,
        strategy_returns=strategy_returns,
        covariance=covariance,
        expected_returns=expected_returns,
    )


def _regularize_covariance(returns: pd.DataFrame, ridge: float = 1e-6) -> pd.DataFrame:
    if returns.empty:
        return pd.DataFrame()
    cov = returns.cov().fillna(0.0)
    diag = np.diag(np.diag(cov.to_numpy(dtype=float)))
    regularized = cov.to_numpy(dtype=float) + diag * 0.05 + np.eye(len(cov), dtype=float) * ridge
    return pd.DataFrame(regularized, index=cov.index, columns=cov.columns)


def latest_score_strength(strategy_signals: pd.DataFrame) -> pd.Series:
    if strategy_signals.empty:
        return pd.Series(dtype=float)
    dated = strategy_signals.copy()
    dated["date"] = pd.to_datetime(dated["date"], format="mixed")
    latest_day = dated["date"].dt.normalize().max()
    latest = dated[dated["date"].dt.normalize().eq(latest_day)].copy()
    grouped = latest.groupby("strategy")["score"].sum().abs().astype(float)
    return grouped.sort_index()


def _apply_caps(weights: pd.Series, caps: dict[str, float] | None) -> tuple[pd.Series, float]:
    normalized = weights.astype(float).clip(lower=0.0)
    total = float(normalized.sum())
    if total <= 0:
        normalized = pd.Series(1.0 / len(normalized), index=normalized.index, dtype=float) if len(normalized) else normalized
    else:
        normalized = normalized / total
    if not caps:
        return normalized, 0.0

    cap_series = pd.Series(caps, dtype=float).reindex(normalized.index).fillna(1.0).clip(lower=0.0, upper=1.0)
    allocated = pd.Series(0.0, index=normalized.index, dtype=float)
    remaining = 1.0
    active = normalized[normalized > 0].index

    while remaining > 1e-12 and len(active) > 0:
        base = normalized.loc[active]
        base_total = float(base.sum())
        if base_total <= 0:
            break
        proposed = base / base_total * remaining
        caps_left = (cap_series.loc[active] - allocated.loc[active]).clip(lower=0.0)
        capped = proposed[proposed > caps_left + 1e-12]
        if capped.empty:
            allocated.loc[active] = allocated.loc[active] + proposed
            remaining = 0.0
            break
        allocated.loc[capped.index] = allocated.loc[capped.index] + caps_left.loc[capped.index]
        remaining = max(0.0, 1.0 - float(allocated.sum()))
        active = caps_left[caps_left > 1e-12].index.difference(capped.index)

    return allocated, max(0.0, 1.0 - float(allocated.sum()))


def _allocation_from_weights(weights: pd.Series, total_cash: float, caps: dict[str, float] | None = None) -> AllocationResult:
    if weights.empty:
        return AllocationResult(allocation=pd.DataFrame(columns=["strategy", "weight", "allocated_cash"]), cash_left=float(total_cash))
    bounded, cash_left_weight = _apply_caps(weights, caps)
    allocation = pd.DataFrame(
        {
            "strategy": bounded.index,
            "weight": bounded.values,
            "allocated_cash": bounded.values * float(total_cash),
        }
    )
    cash_left = float(total_cash * cash_left_weight)
    return AllocationResult(allocation=allocation, cash_left=cash_left)


def equal_allocate_strategy_capital(
    strategy_signals: pd.DataFrame,
    total_cash: float,
    caps: dict[str, float] | None = None,
) -> AllocationResult:
    strategies = latest_score_strength(strategy_signals).index
    if len(strategies) == 0:
        return AllocationResult(allocation=pd.DataFrame(columns=["strategy", "weight", "allocated_cash"]), cash_left=float(total_cash))
    weights = pd.Series(1.0 / len(strategies), index=strategies, dtype=float)
    return _allocation_from_weights(weights, total_cash, caps)


def risk_contributions(weights: pd.Series, covariance: pd.DataFrame) -> pd.Series:
    if weights.empty or covariance.empty:
        return pd.Series(dtype=float)
    aligned_cov = covariance.reindex(index=weights.index, columns=weights.index).fillna(0.0)
    vector = weights.to_numpy(dtype=float)
    marginal = aligned_cov.to_numpy(dtype=float) @ vector
    contributions = vector * marginal
    total = float(contributions.sum())
    if total <= 0:
        return pd.Series(np.zeros(len(weights), dtype=float), index=weights.index)
    return pd.Series(contributions / total, index=weights.index)


def risk_parity_weights(
    covariance: pd.DataFrame,
    *,
    max_iter: int = 2_000,
    tol: float = 1e-6,
) -> pd.Series:
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


def risk_parity_allocate_strategy_capital(
    strategy_returns: pd.DataFrame,
    total_cash: float,
    caps: dict[str, float] | None = None,
    *,
    history_window: int = 40,
) -> AllocationResult:
    if strategy_returns.empty:
        return AllocationResult(allocation=pd.DataFrame(columns=["strategy", "weight", "allocated_cash"]), cash_left=float(total_cash))
    returns_only = strategy_returns.set_index("date").astype(float).tail(history_window)
    covariance = _regularize_covariance(returns_only)
    weights = risk_parity_weights(covariance)
    return _allocation_from_weights(weights, total_cash, caps)


def portfolio_utility(
    weights: pd.Series,
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    *,
    risk_aversion: float = 4.0,
) -> float:
    if weights.empty:
        return float("-inf")
    mu = expected_returns.reindex(weights.index).fillna(0.0).to_numpy(dtype=float)
    cov = covariance.reindex(index=weights.index, columns=weights.index).fillna(0.0).to_numpy(dtype=float)
    vector = weights.to_numpy(dtype=float)
    expected = float(mu @ vector)
    variance = float(vector @ cov @ vector)
    return expected - risk_aversion * variance


def optimized_portfolio_weights(
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    *,
    risk_aversion: float = 4.0,
) -> tuple[pd.Series, str]:
    if covariance.empty:
        return pd.Series(dtype=float), "empty"
    names = list(covariance.index)
    mu = expected_returns.reindex(names).fillna(0.0)
    cov = covariance.reindex(index=names, columns=names).fillna(0.0)
    inv = np.linalg.pinv(cov.to_numpy(dtype=float))
    raw = inv @ mu.to_numpy(dtype=float)
    raw_weights = pd.Series(np.clip(raw, 0.0, None), index=names, dtype=float)
    if float(raw_weights.sum()) <= 0:
        raw_weights = pd.Series(1.0 / len(names), index=names, dtype=float)

    min_var = pd.Series(np.clip(inv @ np.ones(len(names), dtype=float), 0.0, None), index=names, dtype=float)
    if float(min_var.sum()) <= 0:
        min_var = pd.Series(1.0 / len(names), index=names, dtype=float)

    candidates = {
        "optimized": raw_weights / raw_weights.sum(),
        "min_variance": min_var / min_var.sum(),
        "equal_fallback": pd.Series(1.0 / len(names), index=names, dtype=float),
    }
    best_name = "equal_fallback"
    best_weights = candidates[best_name]
    best_utility = float("-inf")
    for name, weights in candidates.items():
        utility = portfolio_utility(weights, mu, cov, risk_aversion=risk_aversion)
        if utility > best_utility:
            best_name = name
            best_weights = weights
            best_utility = utility
    return best_weights, best_name


def optimized_allocate_strategy_capital(
    strategy_returns: pd.DataFrame,
    total_cash: float,
    caps: dict[str, float] | None = None,
    *,
    history_window: int = 40,
    risk_aversion: float = 4.0,
) -> tuple[AllocationResult, str, pd.Series, pd.DataFrame]:
    if strategy_returns.empty:
        empty = AllocationResult(allocation=pd.DataFrame(columns=["strategy", "weight", "allocated_cash"]), cash_left=float(total_cash))
        return empty, "empty", pd.Series(dtype=float), pd.DataFrame()
    returns_only = strategy_returns.set_index("date").astype(float).tail(history_window)
    covariance = _regularize_covariance(returns_only)
    expected_returns = returns_only.mean()
    weights, mode = optimized_portfolio_weights(expected_returns, covariance, risk_aversion=risk_aversion)
    return _allocation_from_weights(weights, total_cash, caps), mode, expected_returns, covariance
