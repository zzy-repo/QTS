from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class OptimizerAdapter:
    """描述一个优化器实现。"""

    name: str
    run: Callable[[pd.DataFrame], pd.DataFrame]
