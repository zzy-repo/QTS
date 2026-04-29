from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from ..data.models import StrategyInput
from .factors import momentum_signal, sharpe_signal, trend_follow_signal


@dataclass(frozen=True)
class FactorAdapter:
    """描述一个可注册的因子实现。"""

    name: str
    run: Callable[[StrategyInput], pd.DataFrame]


_FACTOR_ADAPTERS: dict[str, FactorAdapter] = {
    "momentum": FactorAdapter(name="momentum", run=momentum_signal),
    "trend": FactorAdapter(name="trend", run=trend_follow_signal),
    "sharpe": FactorAdapter(name="sharpe", run=sharpe_signal),
}


def build_factor_adapters() -> dict[str, FactorAdapter]:
    """构建可用因子集合。"""
    return dict(_FACTOR_ADAPTERS)


def get_factor_adapter(kind: str) -> FactorAdapter:
    """按名称获取单个因子实现。"""
    adapter = _FACTOR_ADAPTERS.get(kind)
    if adapter is None:
        raise ValueError(f"不支持的因子类型: {kind}")
    return adapter
