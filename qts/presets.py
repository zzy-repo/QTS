from __future__ import annotations

from .config import (
    build_system_from_config,
    default_qts_config,
    load_market_from_config,
    load_qts_config,
)
from .engine import MultiDecisionSystem, StrategySpec, summarize_system_run


def build_default_strategies() -> list[StrategySpec]:
    return build_system_from_config(default_qts_config()).strategies


def build_default_system() -> MultiDecisionSystem:
    return build_system_from_config(default_qts_config())


def run_demo(config_path: str | None = None):
    config = load_qts_config(config_path)
    market = load_market_from_config(config)
    system = build_system_from_config(config)
    result = system.run(market)
    summary = summarize_system_run(result)
    return market, system, result, summary
