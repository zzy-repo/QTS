from __future__ import annotations

from typing import Callable

import pandas as pd

from ....data.models import StrategyInput
from ....factor import get_factor_adapter


def _strategy_input(data: StrategyInput, *, lookback: int, top_n: int) -> StrategyInput:
    """基于策略参数重建输入对象。"""
    return StrategyInput(
        close=data.close,
        volume=data.volume,
        amount=data.amount,
        lookback=lookback,
        top_n=top_n,
    )


def build_single_factor_strategy(
    factor_kind: str,
    lookback: int,
    top_n: int,
) -> Callable[[StrategyInput], pd.DataFrame]:
    """把单因子实现包装成单因子策略。"""
    factor_fn = get_factor_adapter(factor_kind).run

    def builder(data: StrategyInput) -> pd.DataFrame:
        return factor_fn(_strategy_input(data, lookback=lookback, top_n=top_n))

    return builder
