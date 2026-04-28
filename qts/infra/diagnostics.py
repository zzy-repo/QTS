from __future__ import annotations

import numpy as np
import pandas as pd


def risk_state_machine(
    equity: pd.Series,
    window: int = 20,
    drawdown_warn: float = -0.03,
    drawdown_halt: float = -0.08,
    vol_warn: float = 0.18,
    vol_halt: float = 0.30,
) -> pd.DataFrame:
    """根据权益曲线生成风险状态。"""
    clean = pd.Series(equity).astype(float).dropna()
    if clean.empty:
        return pd.DataFrame(columns=["equity", "rolling_return", "rolling_vol", "drawdown", "state"])
    returns = clean.pct_change().fillna(0.0)
    rolling_vol = returns.rolling(window, min_periods=max(3, window // 2)).std(ddof=0) * np.sqrt(252)
    rolling_return = returns.rolling(window, min_periods=max(3, window // 2)).mean() * 252
    drawdown = clean / clean.cummax() - 1.0
    states: list[str] = []
    for dd, vol in zip(drawdown, rolling_vol.fillna(0.0)):
        if dd <= drawdown_halt or vol >= vol_halt:
            states.append("halt")
        elif dd <= drawdown_warn or vol >= vol_warn:
            states.append("caution")
        else:
            states.append("normal")
    return pd.DataFrame(
        {
            "equity": clean,
            "rolling_return": rolling_return,
            "rolling_vol": rolling_vol,
            "drawdown": drawdown,
            "state": states,
        }
    )
