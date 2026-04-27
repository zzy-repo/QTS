from __future__ import annotations

from .config import (
    build_system_from_config,
    default_qts_config,
    load_market_from_config,
    load_qts_config,
)
from .engine import MultiDecisionSystem
from .reporter import summarize_system_run
from .specs import StrategySpec


def build_default_strategies() -> list[StrategySpec]:
    """构建默认策略列表。"""
    return build_system_from_config(default_qts_config()).strategies


def build_default_system() -> MultiDecisionSystem:
    """构建默认系统。"""
    return build_system_from_config(default_qts_config())


def run_demo(config_path: str | None = None):
    """运行默认 demo。"""
    config = load_qts_config(config_path)
    market = load_market_from_config(config)
    system = build_system_from_config(config)
    result = system.run(market)
    summary = summarize_system_run(result)
    return market, system, result, summary
