from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils import require_volatility


def blend_weight_optimizer(signals: pd.DataFrame, score_weight: float = 0.5) -> pd.DataFrame:
    """在得分和倒波动率之间做加权混合。"""
    if signals.empty:
        return pd.DataFrame(columns=["date", "symbol", "weight", "optimizer"])
    volatility = require_volatility(signals, "blend")
    score_weight = float(min(max(score_weight, 0.0), 1.0))
    inv_weight = 1.0 - score_weight
    rows: list[dict[str, object]] = []
    for date, group in signals.groupby("date"):
        scores = pd.to_numeric(group["score"], errors="coerce").abs()
        score_total = float(scores.sum())
        score_component = scores / score_total if score_total > 0 else pd.Series(1.0 / len(group), index=group.index)
        vols = volatility.loc[group.index].replace(0.0, np.nan)
        inv = 1.0 / vols
        inv = inv.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        inv_total = float(inv.sum())
        inv_component = inv / inv_total if inv_total > 0 else pd.Series(1.0 / len(group), index=group.index)
        weight_series = score_weight * score_component + inv_weight * inv_component
        total = float(weight_series.sum())
        if total > 0:
            weight_series = weight_series / total
        else:
            weight_series = pd.Series(1.0 / len(group), index=group.index)
        for idx, row in group.iterrows():
            rows.append({"date": date, "symbol": row["symbol"], "weight": float(weight_series.loc[idx]), "optimizer": "blend"})
    return pd.DataFrame(rows)
