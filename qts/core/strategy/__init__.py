"""Core strategy layer."""

from typing import Callable

import pandas as pd

from ..data.models import StrategyInput
from ..plugins import collect_strategy_adapters
from .base import StrategyAdapter
from .engine import SignalGenerator
from .specs import StrategySpec
from .validators import validate_strategy_output


def build_strategy_adapters() -> dict[str, StrategyAdapter]:
    """通过插件系统收集可用策略。"""
    return collect_strategy_adapters()


def get_strategy_adapter(kind: str) -> StrategyAdapter:
    """按名称获取单个策略构建器。"""
    adapter = build_strategy_adapters().get(kind)
    if adapter is None:
        raise ValueError(f"不支持的策略类型: {kind}")
    return adapter


def build_strategy_builder(
    strategy_kind: str,
    *,
    factor_kinds: list[str],
    factor_weights: dict[str, float] | None,
    lookback: int,
    top_n: int,
) -> Callable[[StrategyInput], pd.DataFrame]:
    """按策略类型和参数构建策略执行入口。"""
    return get_strategy_adapter(strategy_kind).build(factor_kinds, dict(factor_weights or {}), lookback, top_n)


def build_strategy_spec(
    name: str,
    *,
    strategy_kind: str,
    factor_kinds: list[str],
    factor_weights: dict[str, float] | None = None,
    lookback: int = 20,
    top_n: int = 3,
) -> StrategySpec:
    """按配置参数构造单个策略规格。"""
    return StrategySpec(
        name=name,
        strategy_kind=strategy_kind,
        factor_kinds=list(factor_kinds),
        factor_weights=dict(factor_weights or {}),
        builder=build_strategy_builder(
            strategy_kind,
            factor_kinds=list(factor_kinds),
            factor_weights=dict(factor_weights or {}),
            lookback=lookback,
            top_n=top_n,
        ),
        lookback=lookback,
        top_n=top_n,
    )

__all__ = [
    "SignalGenerator",
    "StrategyAdapter",
    "StrategySpec",
    "build_strategy_adapters",
    "build_strategy_builder",
    "build_strategy_spec",
    "get_strategy_adapter",
    "validate_strategy_output",
]
