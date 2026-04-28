from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.models import StrategyInput


def _serialize_ts(value: object) -> str:
    """把时间值序列化为字符串。"""
    ts = pd.Timestamp(value)
    if ts.time() == pd.Timestamp(ts.date()).time():
        return ts.strftime("%Y-%m-%d")
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def momentum_signal(data: StrategyInput) -> pd.DataFrame:
    """生成动量策略信号。"""
    close = data.close.copy()
    momentum = close.pct_change(data.lookback)
    rows: list[dict[str, object]] = []
    for date in close.index[data.lookback:]:
        row = momentum.loc[date].dropna().sort_values(ascending=False).head(data.top_n)
        if row.empty:
            continue
        weight = 1.0 / len(row)
        for rank, (symbol, score) in enumerate(row.items(), start=1):
            rows.append({"date": _serialize_ts(date), "symbol": symbol, "rank": rank, "score": float(score), "weight": weight})
    return pd.DataFrame(rows)


def trend_follow_signal(data: StrategyInput) -> pd.DataFrame:
    """生成趋势跟随策略信号。"""
    close = data.close.copy()
    short = close.pct_change(max(2, data.lookback // 2))
    long = close.pct_change(data.lookback)
    rows: list[dict[str, object]] = []
    for date in close.index[data.lookback:]:
        short_row = short.loc[date]
        long_row = long.loc[date]
        score = (short_row.fillna(0.0) + long_row.fillna(0.0)) / 2.0
        selected = score.sort_values(ascending=False).head(data.top_n)
        if selected.empty:
            continue
        total = float(selected.abs().sum())
        for rank, (symbol, value) in enumerate(selected.items(), start=1):
            weight = float(abs(value) / total) if total else 1.0 / len(selected)
            rows.append({"date": _serialize_ts(date), "symbol": symbol, "rank": rank, "score": float(value), "weight": weight})
    return pd.DataFrame(rows)


def validate_strategy_output(signal: pd.DataFrame) -> list[str]:
    """校验策略输出的基础格式。"""
    issues: list[str] = []
    required = {"date", "symbol", "weight"}
    if not required.issubset(signal.columns):
        return [f"missing columns: {', '.join(sorted(required - set(signal.columns)))}"]
    if signal["weight"].isna().any():
        issues.append("weight contains null values")
    if (signal["weight"] < 0).any():
        issues.append("weight contains negative values")
    grouped = signal.groupby("date")["weight"].sum()
    if not grouped.empty and not np.isfinite(grouped).all():
        issues.append("weight sum contains non-finite values")
    return issues
