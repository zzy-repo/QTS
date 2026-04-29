"""Deprecated compatibility layer for legacy optimizer imports."""

from .optimizers import (
    OptimizerAdapter,
    blend_weight_optimizer,
    build_optimizers,
    capped_optimizer,
    equal_weight_optimizer,
    inverse_vol_optimizer,
    score_weight_optimizer,
)

__all__ = [
    "OptimizerAdapter",
    "blend_weight_optimizer",
    "build_optimizers",
    "capped_optimizer",
    "equal_weight_optimizer",
    "inverse_vol_optimizer",
    "score_weight_optimizer",
]
