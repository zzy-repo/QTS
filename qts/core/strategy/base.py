from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from ..data.models import StrategyInput


@dataclass(frozen=True)
class StrategyAdapter:
    """描述一个可注册的策略构建器。"""

    name: str
    build: Callable[[list[str], dict[str, float], int, int], Callable[[StrategyInput], pd.DataFrame]]
