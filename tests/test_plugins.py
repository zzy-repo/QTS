from __future__ import annotations

import pandas as pd
import pytest

from qts.core import hookimpl, plugin_context, register_plugin
from qts.core.data.models import StrategyInput
from qts.core.factor import FactorAdapter, build_factor_adapters
from qts.core.optimize.optimizers import OptimizerAdapter, build_optimizers
from qts.core.portfolio.allocators import AllocationResult, AllocatorAdapter, build_allocators
from qts.core.strategy import build_strategy_spec


class DemoPlugin:
    @hookimpl
    def qts_register_factors(self):
        def constant_signal(data: StrategyInput) -> pd.DataFrame:
            rows: list[dict[str, object]] = []
            for date in data.close.index[data.lookback:]:
                for rank, symbol in enumerate(data.close.columns[: data.top_n], start=1):
                    rows.append(
                        {
                            "date": date.strftime("%Y-%m-%d"),
                            "symbol": symbol,
                            "rank": rank,
                            "score": 1.0,
                        }
                    )
            return pd.DataFrame(rows)

        return [FactorAdapter(name="constant", run=constant_signal)]

    @hookimpl
    def qts_register_strategies(self):
        def build_ranked_strategy(
            factor_kinds: list[str],
            factor_weights: dict[str, float],
            lookback: int,
            top_n: int,
        ):
            def builder(data: StrategyInput) -> pd.DataFrame:
                rows: list[dict[str, object]] = []
                for date in data.close.index[lookback:]:
                    for rank, symbol in enumerate(data.close.columns[:top_n], start=1):
                        rows.append(
                            {
                                "date": date.strftime("%Y-%m-%d"),
                                "symbol": symbol,
                                "rank": rank,
                                "score": float(top_n - rank + 1),
                                "weight": 1.0 / top_n,
                            }
                        )
                return pd.DataFrame(rows)

            return builder

        from qts.core.strategy.base import StrategyAdapter

        return [StrategyAdapter(name="ranked", build=build_ranked_strategy)]

    @hookimpl
    def qts_register_optimizers(self, capped_cap: float):
        def passthrough(signals: pd.DataFrame) -> pd.DataFrame:
            return signals.copy()

        return [OptimizerAdapter(name="passthrough", run=passthrough)]

    @hookimpl
    def qts_register_allocators(self):
        def equal_cash(
            strategy_signals: pd.DataFrame,
            total_cash: float,
            caps: dict[str, float] | None = None,
            context=None,
        ) -> AllocationResult:
            strategies = sorted(strategy_signals["strategy"].dropna().astype(str).unique().tolist())
            if not strategies:
                return AllocationResult(allocation=pd.DataFrame(columns=["strategy", "allocated_cash"]), cash_left=float(total_cash))
            per_strategy = float(total_cash) / len(strategies)
            frame = pd.DataFrame({"strategy": strategies, "allocated_cash": per_strategy})
            return AllocationResult(allocation=frame, cash_left=0.0)

        return [AllocatorAdapter(name="flat_cash", run=equal_cash)]


def test_runtime_plugin_registration_exposes_all_extension_points() -> None:
    with plugin_context([(DemoPlugin(), "demo-plugin")]):
        assert "constant" in build_factor_adapters()
        assert "passthrough" in build_optimizers()
        assert "flat_cash" in build_allocators()


def test_custom_strategy_plugin_can_build_executable_spec() -> None:
    with plugin_context([(DemoPlugin(), "demo-plugin")]):
        market = pd.DataFrame(
            {
                "000001": [10.0, 11.0, 12.0, 13.0],
                "000002": [9.0, 9.5, 10.0, 10.5],
            },
            index=pd.bdate_range("2024-01-02", periods=4),
        )
        spec = build_strategy_spec(
            "demo",
            strategy_kind="ranked",
            factor_kinds=["constant"],
            lookback=1,
            top_n=2,
        )

        signals = spec.builder(StrategyInput(close=market, volume=market, amount=market, lookback=1, top_n=2))

        assert not signals.empty
        assert set(signals.columns) >= {"date", "symbol", "rank", "score", "weight"}
        assert signals.groupby("date")["weight"].sum().round(8).eq(1.0).all()


def test_register_plugin_rejects_mutating_default_runtime() -> None:
    with pytest.raises(RuntimeError, match="默认插件运行时不可变"):
        register_plugin(DemoPlugin(), name="forbidden")


def test_plugin_context_does_not_leak_runtime_mutations() -> None:
    assert "constant" not in build_factor_adapters()
    with plugin_context([(DemoPlugin(), "demo-plugin")]):
        assert "constant" in build_factor_adapters()
    assert "constant" not in build_factor_adapters()


class BrokenFactorPlugin:
    @hookimpl
    def qts_register_factors(self):
        return [object()]


def test_plugin_collection_rejects_invalid_adapter_types() -> None:
    with plugin_context([(BrokenFactorPlugin(), "broken-plugin")]):
        with pytest.raises(TypeError, match="factor 插件返回了错误类型"):
            build_factor_adapters()
