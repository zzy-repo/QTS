from __future__ import annotations

import pandas as pd

from ..score import score_weight_optimizer


def capped_optimizer(signals: pd.DataFrame, cap: float = 0.4) -> pd.DataFrame:
    """生成带权重上限的目标权重。"""
    frame = score_weight_optimizer(signals)
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["weight"] = frame["weight"].clip(lower=0.0, upper=cap)

    def _normalize(group: pd.Series) -> pd.Series:
        total = float(group.sum())
        return group / total if total > 0 else group

    frame["weight"] = frame.groupby("date")["weight"].transform(_normalize)
    frame["optimizer"] = "capped"
    return frame
