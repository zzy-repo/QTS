"""Optimizer package."""

from .base import OptimizerAdapter
from .blend import blend_weight_optimizer
from .capped import capped_optimizer
from .equal import equal_weight_optimizer
from .inv_vol import inverse_vol_optimizer
from .score import score_weight_optimizer
from ...plugins import collect_optimizer_adapters


def build_optimizers(capped_cap: float = 0.4) -> dict[str, OptimizerAdapter]:
    """通过插件系统收集可用优化器。"""
    return collect_optimizer_adapters(capped_cap=capped_cap)


def get_optimizer(mode: str, *, capped_cap: float = 0.4) -> OptimizerAdapter:
    """按名称获取单个优化器实现。"""
    optimizer = build_optimizers(capped_cap=capped_cap).get(mode)
    if optimizer is None:
        raise ValueError(f"未知的优化器模式：{mode}")
    return optimizer

__all__ = [
    "OptimizerAdapter",
    "blend_weight_optimizer",
    "build_optimizers",
    "capped_optimizer",
    "equal_weight_optimizer",
    "get_optimizer",
    "inverse_vol_optimizer",
    "score_weight_optimizer",
]
