from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from ..data.models import StrategyInput


@dataclass(frozen=True)
class FactorAdapter:
    """描述一个可注册的因子实现。"""

    name: str
    run: Callable[[StrategyInput], pd.DataFrame]
