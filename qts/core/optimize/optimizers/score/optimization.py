from __future__ import annotations

import pandas as pd


def score_weight_optimizer(signals: pd.DataFrame) -> pd.DataFrame:
    """按信号得分生成目标权重。"""
    if signals.empty:
        return pd.DataFrame(columns=["date", "symbol", "weight", "optimizer"])
    rows: list[dict[str, object]] = []
    for date, group in signals.groupby("date"):
        scores = group["score"].abs().astype(float)
        total = float(scores.sum())
        if total <= 0:
            weight = 1.0 / len(group) if len(group) else 0.0
            for symbol in group["symbol"]:
                rows.append({"date": date, "symbol": symbol, "weight": weight, "optimizer": "score"})
            continue
        for _, row in group.iterrows():
            rows.append({"date": date, "symbol": row["symbol"], "weight": float(abs(row["score"]) / total), "optimizer": "score"})
    return pd.DataFrame(rows)
