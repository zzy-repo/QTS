from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .optimization import build_optimizers


@dataclass(frozen=True)
class Optimizer:
    """把信号转换成目标权重。"""

    mode: str = "score"
    capped_cap: float = 0.4

    def optimize(self, signals: pd.DataFrame) -> pd.DataFrame:
        """执行选定的优化器。"""
        optimizer = build_optimizers(capped_cap=self.capped_cap).get(self.mode)
        if optimizer is None:
            raise ValueError(f"未知的优化器模式：{self.mode}")
        return optimizer.run(signals)
