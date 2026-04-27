from __future__ import annotations

from .data_source import DEFAULT_UNIVERSE, load_market_panel
from .engine import MultiDecisionSystem, StrategySpec, summarize_system_run
from .models import StrategyInput
from .strategy import momentum_signal, trend_follow_signal


def build_default_strategies() -> list[StrategySpec]:
    return [
        StrategySpec(
            name="momentum",
            builder=lambda data: momentum_signal(StrategyInput(close=data.close, volume=data.volume, amount=data.amount, lookback=20, top_n=3)),
            lookback=20,
            top_n=3,
        ),
        StrategySpec(
            name="trend",
            builder=lambda data: trend_follow_signal(StrategyInput(close=data.close, volume=data.volume, amount=data.amount, lookback=30, top_n=3)),
            lookback=30,
            top_n=3,
        ),
    ]


def build_default_system() -> MultiDecisionSystem:
    return MultiDecisionSystem(
        strategies=build_default_strategies(),
        optimizer_mode="score",
        execution_mode="backtest",
        initial_cash=1_000_000.0,
        lot_size=100,
        capital_caps={"momentum": 0.65, "trend": 0.65},
    )


def run_demo(start_date: str = "20240102", end_date: str = "20240315"):
    market = load_market_panel(DEFAULT_UNIVERSE, start_date, end_date)
    system = build_default_system()
    result = system.run(market)
    summary = summarize_system_run(result)
    return market, system, result, summary
