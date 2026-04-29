from __future__ import annotations

import numpy as np
import pandas as pd

from ...data.models import StrategyInput
from ...utils import serialize_ts


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
                    "date": serialize_ts(date),
                    "symbol": symbol,
                    "rank": rank,
                    "score": float(value),
                    "weight": weight,
                    "volatility": float(rolling_vol.loc[date].get(symbol, np.nan)),
                    "adv": float(adv.loc[date].get(symbol, np.nan)) if adv is not None else np.nan,
                }
            )
    return pd.DataFrame(rows)
