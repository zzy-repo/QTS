from __future__ import annotations

import pandas as pd


def require_volatility(signals: pd.DataFrame, optimizer_name: str) -> pd.Series:
    """确保依赖波动率的优化器拿到明确可用的字段。"""
    if "volatility" not in signals.columns:
        raise ValueError(f"优化器需要 volatility 列: {optimizer_name}")
    return pd.to_numeric(signals["volatility"], errors="coerce")
