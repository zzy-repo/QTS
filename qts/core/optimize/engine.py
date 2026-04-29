from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .optimizers import OptimizerAdapter, get_optimizer


@dataclass(frozen=True)
class Optimizer:
    """把信号转换成目标权重。"""

    mode: str = "score"
    capped_cap: float = 0.4
    _adapter: OptimizerAdapter = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_adapter", get_optimizer(self.mode, capped_cap=self.capped_cap))

    def optimize(self, signals: pd.DataFrame) -> pd.DataFrame:
        """执行选定的优化器。"""
        return self._adapter.run(signals)
