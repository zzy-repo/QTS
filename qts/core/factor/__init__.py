"""Core factor layer."""

from .base import FactorAdapter
from ..plugins import collect_factor_adapters


def build_factor_adapters() -> dict[str, FactorAdapter]:
    """通过插件系统收集可用因子。"""
    return collect_factor_adapters()


def get_factor_adapter(kind: str) -> FactorAdapter:
    """按名称获取单个因子实现。"""
    adapter = build_factor_adapters().get(kind)
    if adapter is None:
        raise ValueError(f"不支持的因子类型: {kind}")
    return adapter

__all__ = [
    "FactorAdapter",
    "build_factor_adapters",
    "get_factor_adapter",
]
