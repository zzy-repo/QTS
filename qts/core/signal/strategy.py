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
    daily_returns = close.pct_change()
    rolling_vol = daily_returns.rolling(data.lookback, min_periods=max(5, data.lookback // 2)).std(ddof=0)
    adv = data.amount.rolling(data.lookback, min_periods=max(5, data.lookback // 2)).mean() if data.amount is not None else None
    momentum = close.pct_change(data.lookback)
    rows: list[dict[str, object]] = []
    for date in close.index[data.lookback:]:
        row = momentum.loc[date].dropna().sort_values(ascending=False).head(data.top_n)
        if row.empty:
            continue
        weight = 1.0 / len(row)
        for rank, (symbol, score) in enumerate(row.items(), start=1):
            rows.append(
                {
                    "date": _serialize_ts(date),
                    "symbol": symbol,
                    "rank": rank,
                    "score": float(score),
                    "weight": weight,
                    "volatility": float(rolling_vol.loc[date].get(symbol, np.nan)),
                    "adv": float(adv.loc[date].get(symbol, np.nan)) if adv is not None else np.nan,
                }
            )
    return pd.DataFrame(rows)


def trend_follow_signal(data: StrategyInput) -> pd.DataFrame:
    """生成趋势跟随策略信号。"""
    close = data.close.copy()
    daily_returns = close.pct_change()
    rolling_vol = daily_returns.rolling(data.lookback, min_periods=max(5, data.lookback // 2)).std(ddof=0)
    adv = data.amount.rolling(data.lookback, min_periods=max(5, data.lookback // 2)).mean() if data.amount is not None else None
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
            rows.append(
                {
                    "date": _serialize_ts(date),
                    "symbol": symbol,
                    "rank": rank,
                    "score": float(value),
                    "weight": weight,
                    "volatility": float(rolling_vol.loc[date].get(symbol, np.nan)),
                    "adv": float(adv.loc[date].get(symbol, np.nan)) if adv is not None else np.nan,
                }
            )
    return pd.DataFrame(rows)


def sharpe_signal(
    data: StrategyInput,
    *,
    adv_quantile: float = 0.50,
    spread_quantile: float = 0.60,
    cap_quantile: float = 0.50,
) -> pd.DataFrame:
    """生成受流动性和市值代理约束的 Sharpe 排序信号。"""
    close = data.close.copy()
    daily_returns = close.pct_change()
    rolling_mean = daily_returns.rolling(data.lookback, min_periods=max(5, data.lookback // 2)).mean()
    rolling_vol = daily_returns.rolling(data.lookback, min_periods=max(5, data.lookback // 2)).std(ddof=0)
    rolling_sharpe = rolling_mean / rolling_vol.replace(0.0, np.nan)
    adv = data.amount.rolling(data.lookback, min_periods=max(5, data.lookback // 2)).mean() if data.amount is not None else None
    spread_proxy = daily_returns.abs().rolling(data.lookback, min_periods=max(5, data.lookback // 2)).mean()
    cap_proxy = close.rolling(data.lookback, min_periods=max(5, data.lookback // 2)).mean()
    rows: list[dict[str, object]] = []
    for date in close.index[data.lookback:]:
        sharpe_row = rolling_sharpe.loc[date].dropna().sort_values(ascending=False)
        if sharpe_row.empty:
            continue
        adv_row = adv.loc[date].reindex(sharpe_row.index) if adv is not None else pd.Series(np.nan, index=sharpe_row.index)
        cap_row = cap_proxy.loc[date].reindex(sharpe_row.index)
        spread_row = spread_proxy.loc[date].reindex(sharpe_row.index)
        filtered = sharpe_row[
            (adv_row >= adv_row.quantile(adv_quantile))
            & (cap_row >= cap_row.quantile(cap_quantile))
            & (spread_row <= spread_row.quantile(spread_quantile))
        ]
        chosen = filtered.head(data.top_n)
        if chosen.empty:
            chosen = sharpe_row.head(data.top_n)
        for rank, (symbol, score) in enumerate(chosen.items(), start=1):
            rows.append(
                {
                    "date": _serialize_ts(date),
                    "symbol": symbol,
                    "rank": rank,
                    "score": float(score),
                    "weight": 1.0 / len(chosen),
                    "volatility": float(rolling_vol.loc[date].get(symbol, np.nan)),
                    "adv": float(adv_row.get(symbol, np.nan)),
                    "cap_proxy": float(cap_row.get(symbol, np.nan)),
                    "spread_proxy": float(spread_row.get(symbol, np.nan)),
                }
            )
    return pd.DataFrame(rows)


def validate_strategy_output(signal: pd.DataFrame) -> list[str]:
    """校验策略输出的基础格式。"""
    issues: list[str] = []
    required = {"date", "symbol", "rank", "score", "weight"}
    if not required.issubset(signal.columns):
        return [f"缺少字段：{', '.join(sorted(required - set(signal.columns)))}"]
    rank = pd.to_numeric(signal["rank"], errors="coerce")
    score = pd.to_numeric(signal["score"], errors="coerce")
    weight = pd.to_numeric(signal["weight"], errors="coerce")
    if rank.isna().any():
        issues.append("rank 列存在空值或非数值")
    if score.isna().any():
        issues.append("score 列存在空值或非数值")
    if signal["weight"].isna().any():
        issues.append("weight 列存在空值")
    if weight.isna().any():
        issues.append("weight 列存在非数值")
    if (weight < 0).any():
        issues.append("weight 列存在负值")
    grouped = weight.groupby(signal["date"]).sum()
    if not grouped.empty and not np.isfinite(grouped).all():
        issues.append("按日期汇总后的 weight 存在非有限值")
    return issues
