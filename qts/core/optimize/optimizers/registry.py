from __future__ import annotations

import pandas as pd

from .base import OptimizerAdapter
from .blend import blend_weight_optimizer
from .capped import capped_optimizer
from .equal import equal_weight_optimizer
from .inv_vol import inverse_vol_optimizer
from .score import score_weight_optimizer


def build_optimizers(capped_cap: float = 0.4) -> dict[str, OptimizerAdapter]:
    """构建可用优化器集合。"""

    def capped_run(signals: pd.DataFrame) -> pd.DataFrame:
        return capped_optimizer(signals, cap=capped_cap)

    def blend_run(signals: pd.DataFrame) -> pd.DataFrame:
        return blend_weight_optimizer(signals, score_weight=0.5)

    return {
        "equal": OptimizerAdapter(name="equal", run=equal_weight_optimizer),
        "score": OptimizerAdapter(name="score", run=score_weight_optimizer),
        "inv_vol": OptimizerAdapter(name="inv_vol", run=inverse_vol_optimizer),
        "blend": OptimizerAdapter(name="blend", run=blend_run),
        "capped": OptimizerAdapter(name="capped", run=capped_run),
    }


def get_optimizer(mode: str, *, capped_cap: float = 0.4) -> OptimizerAdapter:
    """按名称获取单个优化器实现。"""
    optimizer = build_optimizers(capped_cap=capped_cap).get(mode)
    if optimizer is None:
        raise ValueError(f"未知的优化器模式：{mode}")
    return optimizer
