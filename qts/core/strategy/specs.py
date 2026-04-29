from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from ..data.models import StrategyInput


@dataclass(frozen=True)
class StrategySpec:
    """描述一个可执行的策略入口。"""

    name: str
    builder: Callable[[StrategyInput], pd.DataFrame]
    strategy_kind: str = "factor"
    factor_kinds: list[str] = field(default_factory=list)
    factor_weights: dict[str, float] = field(default_factory=dict)
    lookback: int = 20
    top_n: int = 3
