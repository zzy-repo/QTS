from __future__ import annotations

import numpy as np
import pandas as pd


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
