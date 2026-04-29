from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from ..data.models import StrategyInput
from .factors import momentum_signal, sharpe_signal, trend_follow_signal
from .specs import StrategySpec


@dataclass(frozen=True)
class SignalAdapter:
    """描述一个可注册的因子实现。"""

    name: str
    run: Callable[[StrategyInput], pd.DataFrame]


def build_signal_adapters() -> dict[str, SignalAdapter]:
    """构建可用因子集合。"""
    return {
        "momentum": SignalAdapter(name="momentum", run=momentum_signal),
        "trend": SignalAdapter(name="trend", run=trend_follow_signal),
        "sharpe": SignalAdapter(name="sharpe", run=sharpe_signal),
    }


def get_signal_adapter(kind: str) -> SignalAdapter:
    """按名称获取单个因子实现。"""
    adapter = build_signal_adapters().get(kind)
    if adapter is None:
        raise ValueError(f"不支持的策略类型: {kind}")
    return adapter


def _strategy_input(data: StrategyInput, *, lookback: int, top_n: int) -> StrategyInput:
    """基于调用时参数重建策略输入。"""
    return StrategyInput(
        close=data.close,
        volume=data.volume,
        amount=data.amount,
        lookback=lookback,
        top_n=top_n,
    )


def build_strategy_builder(kind: str, *, lookback: int, top_n: int) -> Callable[[StrategyInput], pd.DataFrame]:
    """把原始因子函数包装成统一的策略构建器。"""
    signal_fn = get_signal_adapter(kind).run

    def builder(data: StrategyInput) -> pd.DataFrame:
        return signal_fn(_strategy_input(data, lookback=lookback, top_n=top_n))

    return builder


def build_strategy_spec(name: str, kind: str, *, lookback: int = 20, top_n: int = 3) -> StrategySpec:
    """按配置参数构造单个策略规格。"""
    return StrategySpec(
        name=name,
        builder=build_strategy_builder(kind, lookback=lookback, top_n=top_n),
        lookback=lookback,
        top_n=top_n,
    )
