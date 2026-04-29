from __future__ import annotations

import pandas as pd


def equal_weight_optimizer(signals: pd.DataFrame) -> pd.DataFrame:
    """生成等权目标权重。"""
    if signals.empty:
        return pd.DataFrame(columns=["date", "symbol", "weight", "optimizer"])
    rows: list[dict[str, object]] = []
    for date, group in signals.groupby("date"):
        symbols = list(group["symbol"])
        if not symbols:
            continue
        weight = 1.0 / len(symbols)
        for symbol in symbols:
            rows.append({"date": date, "symbol": symbol, "weight": weight, "optimizer": "equal"})
    return pd.DataFrame(rows)
