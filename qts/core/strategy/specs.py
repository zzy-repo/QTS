from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from ..data.models import StrategyInput


@dataclass(frozen=True)
class StrategySpec:
    """描述一个可执行的策略入口。"""

    name: str
    strategy_kind: str
    factor_kind: str
    builder: Callable[[StrategyInput], pd.DataFrame]
    lookback: int = 20
    top_n: int = 3
