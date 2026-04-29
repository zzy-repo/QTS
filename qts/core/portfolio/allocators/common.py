from __future__ import annotations

import numpy as np
import pandas as pd

from ...data.models import MarketPanel
from .base import AllocationContext, AllocationResult


def latest_strategy_signal_frame(strategy_signals: pd.DataFrame) -> pd.DataFrame:
    """保留最新交易日的全部策略信号。"""
    if strategy_signals.empty:
        return pd.DataFrame(columns=list(strategy_signals.columns))
    dated = strategy_signals.copy()
    dated["date"] = pd.to_datetime(dated["date"], format="mixed")
    latest_day = dated["date"].dt.normalize().max()
    latest = dated[dated["date"].dt.normalize().eq(latest_day)].copy()
    latest["score"] = pd.to_numeric(latest["score"], errors="coerce").fillna(0.0)
    latest["weight"] = pd.to_numeric(latest["weight"], errors="coerce").fillna(0.0)
    if "volatility" in latest.columns:
        latest["volatility"] = pd.to_numeric(latest["volatility"], errors="coerce")
    else:
        latest["volatility"] = np.nan
    return latest


def aggregate_strategy_statistics(strategy_signals: pd.DataFrame) -> pd.DataFrame:
    """把资产级信号压缩成策略级得分和波动率统计。"""
    latest = latest_strategy_signal_frame(strategy_signals)
    if latest.empty:
        return pd.DataFrame(columns=["strategy", "score_strength", "volatility", "selection_count"])

    rows: list[dict[str, object]] = []
    for strategy, group in latest.groupby("strategy"):
        scores = group["score"].abs().astype(float)
        base_weights = group["weight"].astype(float).clip(lower=0.0)
        weight_total = float(base_weights.sum())
        if weight_total <= 0:
            base_weights = pd.Series(1.0 / len(group), index=group.index, dtype=float)
        else:
            base_weights = base_weights / weight_total

        volatility = group["volatility"].astype(float).replace([np.inf, -np.inf], np.nan)
        valid_vol = volatility.notna() & (volatility > 0)
        if valid_vol.any():
            vol_weights = base_weights.loc[valid_vol]
            vol_weights = vol_weights / float(vol_weights.sum()) if float(vol_weights.sum()) > 0 else pd.Series(
                1.0 / int(valid_vol.sum()),
                index=group.index[valid_vol],
                dtype=float,
            )
            aggregated_vol = float((vol_weights * volatility.loc[valid_vol]).sum())
        else:
            aggregated_vol = np.nan

        rows.append(
            {
                "strategy": str(strategy),
                "score_strength": float(scores.sum()),
                "volatility": aggregated_vol,
                "selection_count": int(len(group)),
            }
        )
    return pd.DataFrame(rows).sort_values("strategy").reset_index(drop=True)


def diagonal_covariance_from_volatility(strategy_stats: pd.DataFrame) -> pd.DataFrame:
    """用策略聚合波动率构造对角协方差矩阵。"""
    if strategy_stats.empty:
        return pd.DataFrame()
    ordered = strategy_stats.set_index("strategy").sort_index()
    volatility = ordered["volatility"].astype(float).replace([np.inf, -np.inf], np.nan)
    valid = volatility[(volatility > 0) & volatility.notna()]
    fallback = float(valid.median()) if not valid.empty else 1.0
    clean = volatility.fillna(fallback).clip(lower=max(fallback * 0.25, 1e-6))
    variances = np.square(clean.to_numpy(dtype=float))
    return pd.DataFrame(np.diag(variances), index=ordered.index, columns=ordered.index)


def regularize_covariance(returns: pd.DataFrame, ridge: float = 1e-6, shrinkage: float = 0.05) -> pd.DataFrame:
    """对策略收益协方差做轻度对角收缩，提升数值稳定性。"""
    if returns.empty:
        return pd.DataFrame()
    cov = returns.cov().fillna(0.0)
    diag = np.diag(np.diag(cov.to_numpy(dtype=float)))
    regularized = cov.to_numpy(dtype=float) + diag * float(shrinkage) + np.eye(len(cov), dtype=float) * float(ridge)
    return pd.DataFrame(regularized, index=cov.index, columns=cov.columns)


def build_strategy_return_history(strategy_signals: pd.DataFrame, market: MarketPanel) -> pd.DataFrame:
    """根据历史策略信号和市场面板重建策略收益序列。"""
    if strategy_signals.empty or market.close.empty:
        return pd.DataFrame()

    next_returns = market.close.sort_index().pct_change().shift(-1)
    if next_returns.empty:
        return pd.DataFrame()

    dated = strategy_signals.copy()
    dated["date"] = pd.to_datetime(dated["date"], format="mixed")
    dated["trade_day"] = dated["date"].dt.normalize()
    dated["weight"] = pd.to_numeric(dated["weight"], errors="coerce").fillna(0.0)
    dated["score"] = pd.to_numeric(dated["score"], errors="coerce").fillna(0.0)

    rows: list[dict[str, object]] = []
    for (trade_day, strategy), group in dated.groupby(["trade_day", "strategy"]):
        if trade_day not in next_returns.index:
            continue
        realized = next_returns.loc[trade_day]
        if realized.isna().all():
            continue
        weights = group["weight"].astype(float).clip(lower=0.0)
        weight_total = float(weights.sum())
        if weight_total <= 0:
            weights = group["score"].abs().astype(float)
            weight_total = float(weights.sum())
        if weight_total <= 0:
            weights = pd.Series(1.0 / len(group), index=group.index, dtype=float)
        else:
            weights = weights / weight_total
        returns = realized.reindex(group["symbol"]).fillna(0.0)
        rows.append(
            {
                "date": trade_day,
                "strategy": str(strategy),
                "return": float(weights.to_numpy(dtype=float) @ returns.to_numpy(dtype=float)),
            }
        )

    if not rows:
        return pd.DataFrame()

    wide = pd.DataFrame(rows).pivot(index="date", columns="strategy", values="return").sort_index()
    return wide.dropna(how="all").reset_index()


def strategy_return_history(strategy_signals: pd.DataFrame, context: AllocationContext | None) -> pd.DataFrame:
    """优先从 context 读取策略收益历史，否则尝试用 market 重建。"""
    if context is None:
        return pd.DataFrame()
    if context.strategy_return_history is not None:
        history = context.strategy_return_history.copy()
        if "date" in history.columns:
            history["date"] = pd.to_datetime(history["date"], format="mixed")
            return history.sort_values("date").reset_index(drop=True)
        return history
    if context.market is not None:
        return build_strategy_return_history(strategy_signals, context.market)
    return pd.DataFrame()


def risk_contributions(weights: pd.Series, covariance: pd.DataFrame) -> pd.Series:
    """计算权重在给定协方差下的风险贡献占比。"""
    if weights.empty or covariance.empty:
        return pd.Series(dtype=float)
    ordered = covariance.reindex(index=weights.index, columns=weights.index).fillna(0.0)
    vector = weights.to_numpy(dtype=float)
    marginal = ordered.to_numpy(dtype=float) @ vector
    contribution = vector * marginal
    total = float(contribution.sum())
    if total <= 0 or not np.isfinite(total):
        return pd.Series(np.zeros(len(weights), dtype=float), index=weights.index)
    return pd.Series(contribution / total, index=weights.index, dtype=float)


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


def finalize_allocation(weights: pd.Series, total_cash: float, caps: dict[str, float] | None = None) -> AllocationResult:
    if weights.empty:
        return AllocationResult(allocation=pd.DataFrame(columns=["strategy", "allocated_cash"]), cash_left=float(total_cash))
    bounded, cash_left_weight = _apply_caps(weights, caps)
    allocation = pd.DataFrame(
        {
            "strategy": bounded.index,
            "allocated_cash": bounded.values * float(total_cash),
        }
    )
    cash_left = float(total_cash * cash_left_weight) if caps else float(total_cash - allocation["allocated_cash"].sum())
    return AllocationResult(allocation=allocation, cash_left=cash_left)
