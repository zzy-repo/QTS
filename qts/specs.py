from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .models import StrategyInput


@dataclass(frozen=True)
class StrategySpec:
    name: str
    builder: Callable[[StrategyInput], pd.DataFrame]
    lookback: int = 20
    top_n: int = 3

