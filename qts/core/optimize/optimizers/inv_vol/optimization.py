from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils import require_volatility


def inverse_vol_optimizer(signals: pd.DataFrame) -> pd.DataFrame:
    """按波动率倒数生成目标权重。"""
    if signals.empty:
        return pd.DataFrame(columns=["date", "symbol", "weight", "optimizer"])
    volatility = require_volatility(signals, "inv_vol")
    rows: list[dict[str, object]] = []
    for date, group in signals.groupby("date"):
        vols = volatility.loc[group.index].replace(0.0, np.nan)
        inv = 1.0 / vols
        inv = inv.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        total = float(inv.sum())
        if total <= 0:
            weight = 1.0 / len(group) if len(group) else 0.0
            for symbol in group["symbol"]:
                rows.append({"date": date, "symbol": symbol, "weight": weight, "optimizer": "inv_vol"})
            continue
        for idx, row in group.iterrows():
            rows.append(
                {
                    "date": date,
                    "symbol": row["symbol"],
                    "weight": float(inv.loc[idx] / total),
                    "optimizer": "inv_vol",
                }
            )
    return pd.DataFrame(rows)
