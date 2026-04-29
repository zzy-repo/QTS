from __future__ import annotations

from typing import Callable

import pandas as pd

from ..data.models import StrategyInput
from .base import StrategyAdapter
from .specs import StrategySpec
from .strategies import build_single_factor_strategy


_STRATEGY_ADAPTERS: dict[str, StrategyAdapter] = {
    "single_factor": StrategyAdapter(name="single_factor", build=build_single_factor_strategy),
}


def build_strategy_adapters() -> dict[str, StrategyAdapter]:
    """构建可用策略集合。"""
    return dict(_STRATEGY_ADAPTERS)


def get_strategy_adapter(kind: str) -> StrategyAdapter:
    """按名称获取单个策略构建器。"""
    adapter = _STRATEGY_ADAPTERS.get(kind)
    if adapter is None:
        raise ValueError(f"不支持的策略类型: {kind}")
    return adapter


def build_strategy_builder(
    strategy_kind: str,
    *,
    factor_kind: str,
    lookback: int,
    top_n: int,
) -> Callable[[StrategyInput], pd.DataFrame]:
    """按策略类型和参数构建策略执行入口。"""
    return get_strategy_adapter(strategy_kind).build(factor_kind, lookback, top_n)


def build_strategy_spec(
    name: str,
    *,
    strategy_kind: str,
    factor_kind: str,
    lookback: int = 20,
    top_n: int = 3,
) -> StrategySpec:
    """按配置参数构造单个策略规格。"""
    return StrategySpec(
        name=name,
        strategy_kind=strategy_kind,
        factor_kind=factor_kind,
        builder=build_strategy_builder(
            strategy_kind,
            factor_kind=factor_kind,
            lookback=lookback,
            top_n=top_n,
        ),
        lookback=lookback,
        top_n=top_n,
    )
