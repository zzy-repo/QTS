from __future__ import annotations

import numpy as np
import pandas as pd

from ...data.models import StrategyInput
from ...utils import serialize_ts


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
                    "date": serialize_ts(date),
                    "symbol": symbol,
                    "rank": rank,
                    "score": float(score),
                    "weight": weight,
                    "volatility": float(rolling_vol.loc[date].get(symbol, np.nan)),
                    "adv": float(adv.loc[date].get(symbol, np.nan)) if adv is not None else np.nan,
                }
            )
    return pd.DataFrame(rows)
