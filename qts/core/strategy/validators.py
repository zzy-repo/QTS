from __future__ import annotations

import numpy as np
import pandas as pd
from pandera.errors import SchemaErrors

from ..frame_schemas import SIGNAL_SCHEMA, collect_schema_issues


def validate_strategy_output(signal: pd.DataFrame) -> list[str]:
    """校验策略输出的基础格式。"""
    if signal.empty:
        return []
    issues: list[str] = []
    try:
        validated = SIGNAL_SCHEMA.validate(signal, lazy=True)
    except SchemaErrors as exc:
        return collect_schema_issues(exc)
    weight = pd.to_numeric(validated["weight"], errors="coerce")
    grouped = weight.groupby(signal["date"]).sum()
    if not grouped.empty and not np.isfinite(grouped).all():
        issues.append("按日期汇总后的 weight 存在非有限值")
    return issues
