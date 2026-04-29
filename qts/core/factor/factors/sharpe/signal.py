from __future__ import annotations

import numpy as np
import pandas as pd

from ....data.models import StrategyInput
from ...utils import serialize_ts


def sharpe_signal(
    data: StrategyInput,
    *,
    adv_quantile: float = 0.50,
    spread_quantile: float = 0.60,
    cap_quantile: float = 0.50,
) -> pd.DataFrame:
    """生成受流动性和市值代理约束的 Sharpe 因子横截面分数。"""
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
        eligible = sharpe_row[
            (adv_row >= adv_row.quantile(adv_quantile))
            & (cap_row >= cap_row.quantile(cap_quantile))
            & (spread_row <= spread_row.quantile(spread_quantile))
        ]
        chosen = eligible if not eligible.empty else sharpe_row
        for rank, (symbol, score) in enumerate(chosen.items(), start=1):
            rows.append(
                {
                    "date": serialize_ts(date),
                    "symbol": symbol,
                    "rank": rank,
                    "score": float(score),
                    "volatility": float(rolling_vol.loc[date].get(symbol, np.nan)),
                    "adv": float(adv_row.get(symbol, np.nan)),
                    "cap_proxy": float(cap_row.get(symbol, np.nan)),
                    "spread_proxy": float(spread_row.get(symbol, np.nan)),
                }
            )
    return pd.DataFrame(rows)
