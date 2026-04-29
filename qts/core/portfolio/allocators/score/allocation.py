from __future__ import annotations

import pandas as pd

from ..base import AllocationContext, AllocationResult


def _apply_caps(weights: pd.Series, caps: dict[str, float]) -> tuple[pd.Series, float]:
    """按比例上限迭代分配权重，并保留无法继续分配的剩余现金。"""
    cap_series = pd.Series(caps, dtype=float).reindex(weights.index).fillna(1.0).clip(lower=0.0, upper=1.0)
    allocated = pd.Series(0.0, index=weights.index, dtype=float)
    remaining = 1.0
    active = weights[weights > 0].index

    while remaining > 0 and len(active) > 0:
        base = weights.loc[active]
        base_total = float(base.sum())
        if base_total <= 0:
            break
        proposed = base / base_total * remaining
        caps_left = (cap_series.loc[active] - allocated.loc[active]).clip(lower=0.0)
        capped = proposed[proposed > caps_left]
        if capped.empty:
            allocated.loc[active] = allocated.loc[active] + proposed
            remaining = 0.0
            break
        allocated.loc[capped.index] = allocated.loc[capped.index] + caps_left.loc[capped.index]
        remaining = max(0.0, 1.0 - float(allocated.sum()))
        active = caps_left[caps_left > 0].index.difference(capped.index)

    return allocated, max(0.0, 1.0 - float(allocated.sum()))


def score_allocate_capital(
    strategy_signals: pd.DataFrame,
    total_cash: float,
    caps: dict[str, float] | None = None,
    *,
    context: AllocationContext | None = None,
) -> AllocationResult:
    """按策略信号分配资金。"""
    if strategy_signals.empty:
        return AllocationResult(allocation=pd.DataFrame(columns=["strategy", "allocated_cash"]), cash_left=total_cash)
    dated = strategy_signals.copy()
    dated["date"] = pd.to_datetime(dated["date"], format="mixed")
    latest_day = dated["date"].dt.normalize().max()
    latest_signals = dated[dated["date"].dt.normalize().eq(latest_day)].copy()
    grouped = latest_signals.groupby("strategy")["score"].sum().abs()
    if grouped.sum() <= 0:
        weights = pd.Series(1.0 / len(grouped), index=grouped.index)
    else:
        weights = grouped / grouped.sum()
    cash_left_weight = 0.0
    if caps:
        weights, cash_left_weight = _apply_caps(weights, caps)
    allocation = pd.DataFrame({"strategy": weights.index, "allocated_cash": weights.values * float(total_cash)})
    cash_left = float(total_cash * cash_left_weight) if caps else float(total_cash - allocation["allocated_cash"].sum())
    return AllocationResult(allocation=allocation, cash_left=cash_left)
