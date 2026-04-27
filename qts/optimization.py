from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class OptimizerAdapter:
    name: str
    run: Callable[[pd.DataFrame], pd.DataFrame]


def equal_weight_optimizer(signals: pd.DataFrame) -> pd.DataFrame:
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


def score_weight_optimizer(signals: pd.DataFrame) -> pd.DataFrame:
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


def capped_optimizer(signals: pd.DataFrame, cap: float = 0.4) -> pd.DataFrame:
    frame = score_weight_optimizer(signals)
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["weight"] = frame["weight"].clip(lower=0.0, upper=cap)
    frame["weight"] = frame.groupby("date")["weight"].transform(lambda s: s / s.sum() if s.sum() > 0 else s)
    frame["optimizer"] = "capped"
    return frame


def build_optimizers() -> dict[str, OptimizerAdapter]:
    return {
        "equal": OptimizerAdapter(name="equal", run=equal_weight_optimizer),
        "score": OptimizerAdapter(name="score", run=score_weight_optimizer),
        "capped": OptimizerAdapter(name="capped", run=lambda signals: capped_optimizer(signals, cap=0.4)),
    }
