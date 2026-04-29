from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import requests

from qts.core.data.models import MarketPanel
from qts.core.data import data_source as data_source_module
from qts.core.data import cache as cache_module
from qts.core.data.models import ExecutionRun
from qts.paths import REPO_ROOT
from qts.core.portfolio.engine import PortfolioManager
from qts.core.portfolio.allocators import build_allocators
from qts.core.portfolio.allocators.score import score_allocate_capital
from qts.core.portfolio.allocators.base import AllocationContext
from qts.core.portfolio.allocators.common import (
    aggregate_strategy_statistics,
    build_strategy_return_history,
    diagonal_covariance_from_volatility,
    risk_contributions,
)
from qts.core.portfolio.engine_allocator import Allocator
from qts.core.portfolio.results import annualized_return, daily_pnl_view
from qts.core.optimize.engine import Optimizer
from qts.core.strategy.engine import SignalGenerator
from qts.core.strategy.specs import StrategySpec
from qts.infra.config import apply_overrides, build_system_from_config, default_qts_config, load_qts_config, save_qts_config
from qts.infra.entrypoints import (
    DEFAULT_ENTRY_CONFIG,
    _report_input_for_backtest,
    run_entry,
)
from qts.infra import logging_utils
from qts.infra.report import build_report, latest_signal_frame, normalize_signal_frame
from qts.infra.models import MarketConfig, StrategyConfig, SystemConfig, QTSConfig


def _build_synthetic_market() -> MarketPanel:
    dates = pd.bdate_range("2024-01-02", periods=45)
    index = dates
    symbols = ["000001", "000002", "600519", "601318", "300750"]
    base = pd.Series(range(len(index)), index=index, dtype=float)
    close = pd.DataFrame({symbol: 100.0 + base * (1.0 + i * 0.1) for i, symbol in enumerate(symbols)}, index=index)
    volume = pd.DataFrame({symbol: 1_000_000.0 + base * (1_000.0 + i * 100.0) for i, symbol in enumerate(symbols)}, index=index)
    amount = close * volume
    return MarketPanel(close=close, volume=volume, amount=amount, source_mode="synthetic-test")


def _build_allocator_market(close: pd.DataFrame) -> MarketPanel:
    volume = pd.DataFrame(1_000_000.0, index=close.index, columns=close.columns)
    amount = close * volume
    return MarketPanel(close=close, volume=volume, amount=amount, source_mode="synthetic-test")


def test_qts_config_round_trip(tmp_path: Path) -> None:
    config = default_qts_config()
    target = tmp_path / "qts.config.json"
    save_qts_config(config, target)

    loaded = load_qts_config(target)

    assert loaded.to_dict() == config.to_dict()


def test_load_qts_config_parses_multi_factor_schema(tmp_path: Path) -> None:
    target = tmp_path / "multi_factor.config.json"
    target.write_text(
        """
        {
          "市场": {
            "标的池": ["000001", "000002"],
            "开始日期": "20240102",
            "结束日期": "20240131"
          },
          "系统": {
            "优化器": "打分",
            "执行器": "回测"
          },
          "策略": [
            {
              "名称": "core_blend",
              "策略类型": "因子策略",
              "因子列表": ["动量", "趋势", "夏普"],
              "因子权重": {"动量": 0.5, "趋势": 0.3, "夏普": 0.2},
              "回看周期": 12,
              "选取数量": 4
            }
          ]
        }
        """.strip(),
        encoding="utf-8",
    )

    loaded = load_qts_config(target)
    strategy = loaded.strategies[0]

    assert strategy.strategy_kind == "factor"
    assert strategy.factor_kinds == ["momentum", "trend", "sharpe"]
    assert strategy.factor_weights == {"momentum": 0.5, "trend": 0.3, "sharpe": 0.2}
    assert strategy.lookback == 12
    assert strategy.top_n == 4


def test_system_builds_and_runs_on_synthetic_market() -> None:
    config = default_qts_config()
    system = build_system_from_config(config)
    market = _build_synthetic_market()

    result = system.run(market)

    assert len(result.strategy_runs) == len(config.strategies)
    assert not result.aggregate_pnl.empty
    assert not result.aggregate_equity.empty
    assert result.snapshot["strategy_names"] == [strategy.name for strategy in config.strategies]
    assert result.snapshot["risk_state_rows"] >= 0


def test_default_entry_config_points_to_repo_root() -> None:
    assert DEFAULT_ENTRY_CONFIG == REPO_ROOT / "configs" / "qts.config.json"


def test_default_market_cache_root_points_to_repo_root() -> None:
    assert cache_module.default_cache_root() == REPO_ROOT / ".cache" / "qts-market"


def test_entry_profiles_generate_expected_reports(monkeypatch) -> None:
    market = _build_synthetic_market()

    from qts.infra import entrypoints as entrypoints_module

    seen_cache_roots: list[Path | None] = []

    def fake_load_market_from_config(config, cache_root=None):
        seen_cache_roots.append(cache_root)
        return market

    monkeypatch.setattr(entrypoints_module, "load_market_from_config", fake_load_market_from_config)

    backtest_run = run_entry(REPO_ROOT / "configs" / "backtest.json")
    close_run = run_entry(REPO_ROOT / "configs" / "close_report.json")
    stock_run = run_entry(REPO_ROOT / "configs" / "stock_selection.json")

    assert "signal_date" in backtest_run.result.aggregate_pnl.columns
    assert backtest_run.result.aggregate_pnl["annualized_return"].nunique(dropna=False) > 1
    aggregate_pnl = backtest_run.result.aggregate_pnl
    expected_annualized = annualized_return(float(aggregate_pnl["cum_return"].iloc[-1]), len(aggregate_pnl))
    assert float(aggregate_pnl["annualized_return"].iloc[-1]) == expected_annualized
    assert close_run.signals["date"].nunique() > 1
    assert stock_run.signals["date"].nunique() > 1
    assert close_run.report["date"].nunique() == 1
    assert stock_run.report["date"].nunique() == 1
    assert "decision" in close_run.report.columns
    assert "selected" in stock_run.report.columns
    assert seen_cache_roots == [None, None, None]


def test_run_loaded_config_preserves_runtime_overrides(monkeypatch) -> None:
    market = _build_synthetic_market()

    from qts.infra import entrypoints as entrypoints_module

    def fake_load_market_from_config(config, cache_root=None):
        assert config.market.start_date == "20240115"
        assert config.market.symbols == ["000001", "600519"]
        return market

    monkeypatch.setattr(entrypoints_module, "load_market_from_config", fake_load_market_from_config)

    config = apply_overrides(
        load_qts_config(REPO_ROOT / "configs" / "backtest.json"),
        start_date="20240115",
        symbols=["000001", "600519"],
        execution_mode="纸面",
    )
    run = entrypoints_module._run_loaded_config(config, config_path=REPO_ROOT / "configs" / "backtest.json")

    assert run.config.market.start_date == "20240115"
    assert run.config.market.symbols == ["000001", "600519"]
    assert run.config.system.execution_mode == "paper"


def test_sharpe_strategy_and_blend_optimizer_run_on_synthetic_market() -> None:
    config = QTSConfig(
        market=MarketConfig(
            symbols=["000001", "000002", "600519", "601318", "300750"],
            start_date="20240102",
            end_date="20240315",
        ),
        system=SystemConfig(
            optimizer_mode="blend",
            execution_mode="backtest",
            initial_cash=300000.0,
            lot_size=100,
            capital_caps={"sharpe": 0.8},
            optimizer_cap=0.4,
            max_adv_pct=0.02,
            slippage_base_bps=1.0,
            slippage_participation_scale=0.035,
            slippage_vol_scale=0.15,
        ),
        strategies=[StrategyConfig(name="sharpe", strategy_kind="factor", factor_kinds=["sharpe"], lookback=15, top_n=3)],
    )
    system = build_system_from_config(config)
    market = _build_synthetic_market()

    result = system.run(market)

    assert not result.aggregate_pnl.empty
    assert "performance" in result.snapshot
    assert result.snapshot["optimizer_mode"] == "blend"
    assert pd.isna(result.snapshot["performance"]["turnover"])


def test_multi_factor_strategy_runs_on_synthetic_market() -> None:
    config = QTSConfig(
        market=MarketConfig(
            symbols=["000001", "000002", "600519", "601318", "300750"],
            start_date="20240102",
            end_date="20240315",
        ),
        system=SystemConfig(
            optimizer_mode="score",
            execution_mode="backtest",
            initial_cash=300000.0,
            lot_size=100,
        ),
        strategies=[
            StrategyConfig(
                name="core_blend",
                strategy_kind="factor",
                factor_kinds=["momentum", "trend", "sharpe"],
                factor_weights={"momentum": 0.4, "trend": 0.3, "sharpe": 0.3},
                lookback=15,
                top_n=3,
            )
        ],
    )
    system = build_system_from_config(config)
    market = _build_synthetic_market()

    result = system.run(market)
    strategy_run = result.strategy_runs[0]

    assert not result.aggregate_pnl.empty
    assert not strategy_run.signals.empty
    assert strategy_run.signals["strategy"].unique().tolist() == ["core_blend"]
    assert "factor_hits" in strategy_run.signals.columns
    assert strategy_run.signals["weight"].ge(0.0).all()


def test_load_market_panel_propagates_unexpected_errors(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(data_source_module, "sync_symbol_history", boom)

    with pytest.raises(RuntimeError, match="boom"):
        data_source_module.load_market_panel(["000001"], "20240102", "20240110")


def test_load_market_panel_falls_back_when_symbol_data_missing(monkeypatch) -> None:
    empty_sync = data_source_module.SyncResult(
        frame=pd.DataFrame(columns=["date", "symbol", "close", "volume", "amount", "provider"]),
        cache_frame=pd.DataFrame(columns=["date", "symbol", "close", "volume", "amount", "provider"]),
        cache_path=Path("/tmp/cache.parquet"),
        state_path=Path("/tmp/state.json"),
        cache_hit=False,
        network_hit=False,
        fetched_ranges=[],
        source_mode="network",
    )

    monkeypatch.setattr(data_source_module, "sync_symbol_history", lambda *args, **kwargs: empty_sync)

    market = data_source_module.load_market_panel(
        ["000001"],
        "20240102",
        "20240110",
        allow_synthetic_fallback=True,
    )

    assert not market.close.empty
    assert market.source_mode == "offline-seed"


def test_build_secid_matches_eastmoney_market_code() -> None:
    assert data_source_module._build_secid("000001") == "0.000001"
    assert data_source_module._build_secid("300750") == "0.300750"
    assert data_source_module._build_secid("600519") == "1.600519"
    assert data_source_module._build_secid("601318") == "1.601318"


def test_fetch_daily_history_falls_back_to_tx_when_eastmoney_fails(monkeypatch) -> None:
    def fail_eastmoney(*args, **kwargs):
        raise requests.exceptions.ProxyError("proxy down")

    def tx_frame(*args, **kwargs):
        frame = pd.DataFrame(
            [
                {
                    "symbol": "600519",
                    "date": "2024-01-02",
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.0,
                    "close": 10.5,
                    "volume": 1000.0,
                    "amount": 10500.0,
                    "amplitude": pd.NA,
                    "pct_change": pd.NA,
                    "change": pd.NA,
                    "turnover": pd.NA,
                }
            ]
        )
        frame.attrs["provider"] = "tx"
        return frame

    monkeypatch.setattr(data_source_module, "_fetch_eastmoney_daily_history", fail_eastmoney)
    monkeypatch.setattr(data_source_module, "_fetch_tx_daily_history", tx_frame)

    frame = data_source_module.fetch_daily_history("600519", "20240102", "20240110")

    assert frame.attrs["provider"] == "tx"
    assert frame.iloc[0]["symbol"] == "600519"


def test_fetch_tx_daily_history_normalizes_volume_and_amount(monkeypatch) -> None:
    sample = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "open": 10.0,
                "close": 12.0,
                "high": 12.5,
                "low": 9.8,
                "amount": 300.0,
            }
        ]
    )

    class _AkModule:
        @staticmethod
        def stock_zh_a_hist_tx(*args, **kwargs):
            return sample

    monkeypatch.setitem(__import__("sys").modules, "akshare", _AkModule())

    frame = data_source_module._fetch_tx_daily_history("000001", "20240102", "20240110")

    assert frame.attrs["provider"] == "tx"
    assert float(frame.iloc[0]["volume"]) == 30000.0
    assert float(frame.iloc[0]["amount"]) == 360000.0


def test_fetch_daily_history_propagates_eastmoney_parse_errors(monkeypatch) -> None:
    def bad_payload(*args, **kwargs):
        raise ValueError("bad payload")

    def tx_frame(*args, **kwargs):
        frame = pd.DataFrame(
            [
                {
                    "symbol": "600519",
                    "date": "2024-01-02",
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.0,
                    "close": 10.5,
                    "volume": 1000.0,
                    "amount": 10500.0,
                    "amplitude": pd.NA,
                    "pct_change": pd.NA,
                    "change": pd.NA,
                    "turnover": pd.NA,
                }
            ]
        )
        frame.attrs["provider"] = "tx"
        return frame

    monkeypatch.setattr(data_source_module, "_fetch_eastmoney_daily_history", bad_payload)
    monkeypatch.setattr(data_source_module, "_fetch_tx_daily_history", tx_frame)

    frame = data_source_module.fetch_daily_history("600519", "20240102", "20240110")

    assert frame.attrs["provider"] == "tx"
    assert frame.iloc[0]["symbol"] == "600519"


def test_missing_ranges_skips_cached_end_day() -> None:
    requested_start = cache_module.parse_date("2024-01-01")
    requested_end = cache_module.parse_date("2024-01-10")
    cached_start = cache_module.parse_date("2024-01-01")
    cached_end = cache_module.parse_date("2024-01-05")

    ranges = cache_module.missing_ranges(requested_start, requested_end, cached_start, cached_end)

    assert ranges == [(cache_module.parse_date("2024-01-06"), cache_module.parse_date("2024-01-10"))]


def test_ensure_history_frame_adds_provider_column_from_attrs() -> None:
    frame = pd.DataFrame(
        [
            {"date": "2024-01-02", "close": 10.0, "volume": 1000.0, "amount": 10000.0},
        ]
    )
    frame.attrs["provider"] = "tx"

    normalized = cache_module.ensure_history_frame(frame, "000001")

    assert "provider" in normalized.columns
    assert normalized.iloc[0]["provider"] == "tx"


def test_portfolio_manager_executes_each_strategy_with_allocated_cash() -> None:
    class _Allocator:
        mode = "score"

        @staticmethod
        def allocate(strategy_signals: pd.DataFrame, *, total_cash: float, caps=None, context=None):
            return score_allocate_capital(strategy_signals, total_cash=total_cash, caps=caps)

    class _Optimizer:
        mode = "test"

        @staticmethod
        def optimize(signals: pd.DataFrame) -> pd.DataFrame:
            return signals[["date", "symbol", "weight"]].copy()

    class _Executor:
        mode = "test"

        def __init__(self) -> None:
            self.calls: list[float] = []

        def execute(self, target, market, *, initial_cash=1_000_000.0, lot_size=100):
            self.calls.append(float(initial_cash))
            pnl = pd.DataFrame(
                [
                    {
                        "date": "2024-01-03",
                        "signal_date": "2024-01-02",
                        "gross_return": 0.01,
                        "equity": initial_cash * 1.01,
                        "cum_return": 0.01,
                    }
                ]
            )
            return ExecutionRun(orders=pd.DataFrame(), holdings=pd.DataFrame(), pnl=pnl)

    strategies = [
        StrategySpec(name="s1", builder=lambda data: pd.DataFrame()),
        StrategySpec(name="s2", builder=lambda data: pd.DataFrame()),
    ]
    strategy_signals = pd.DataFrame(
        [
            {"date": "2024-01-02", "symbol": "000001", "weight": 1.0, "strategy": "s1", "score": 1.0},
            {"date": "2024-01-02", "symbol": "000002", "weight": 1.0, "strategy": "s2", "score": 3.0},
        ]
    )
    executor = _Executor()

    result = PortfolioManager(initial_cash=1000.0).build(
        strategies=strategies,
        strategy_signals=strategy_signals,
        market=_build_synthetic_market(),
        allocator=_Allocator(),
        optimizer=_Optimizer(),
        executor=executor,
    )

    assert executor.calls == [250.0, 750.0]
    assert [run.allocation_cash for run in result.strategy_runs] == [250.0, 750.0]


def test_portfolio_manager_preserves_multiple_signal_dates_for_same_realization_day() -> None:
    class _Allocator:
        mode = "score"

        @staticmethod
        def allocate(strategy_signals: pd.DataFrame, *, total_cash: float, caps=None, context=None):
            return score_allocate_capital(strategy_signals, total_cash=total_cash, caps=caps)

    class _Optimizer:
        mode = "test"

        @staticmethod
        def optimize(signals: pd.DataFrame) -> pd.DataFrame:
            return signals[["date", "symbol", "weight"]].copy()

    class _Executor:
        mode = "test"

        @staticmethod
        def execute(target, market, *, initial_cash=1_000_000.0, lot_size=100):
            signal_date = str(target["date"].iloc[0])
            pnl = pd.DataFrame(
                [
                    {
                        "date": "2024-01-03",
                        "signal_date": signal_date,
                        "gross_return": 0.01,
                        "equity": initial_cash * 1.01,
                        "cum_return": 0.01,
                    }
                ]
            )
            return ExecutionRun(orders=pd.DataFrame(), holdings=pd.DataFrame(), pnl=pnl)

    strategies = [
        StrategySpec(name="s1", builder=lambda data: pd.DataFrame()),
        StrategySpec(name="s2", builder=lambda data: pd.DataFrame()),
    ]
    strategy_signals = pd.DataFrame(
        [
            {"date": "2024-01-02 09:35:00", "symbol": "000001", "weight": 1.0, "strategy": "s1", "score": 1.0},
            {"date": "2024-01-02 14:55:00", "symbol": "000002", "weight": 1.0, "strategy": "s2", "score": 1.0},
        ]
    )

    result = PortfolioManager(initial_cash=1000.0).build(
        strategies=strategies,
        strategy_signals=strategy_signals,
        market=_build_synthetic_market(),
        allocator=_Allocator(),
        optimizer=_Optimizer(),
        executor=_Executor(),
    )

    assert result.aggregate_pnl["signal_date"].tolist() == ["2024-01-02 09:35:00", "2024-01-02 14:55:00"]
    assert result.aggregate_pnl["equity"].tolist() == [1010.0, 1010.0]
    assert result.aggregate_pnl["cum_return"].tolist() == pytest.approx([0.01, 0.01])


def test_portfolio_manager_exposes_cash_left_in_aggregate_semantics() -> None:
    class _Allocator:
        mode = "score"

        @staticmethod
        def allocate(strategy_signals: pd.DataFrame, *, total_cash: float, caps=None, context=None):
            return score_allocate_capital(strategy_signals, total_cash=total_cash, caps=caps)

    class _Optimizer:
        mode = "test"

        @staticmethod
        def optimize(signals: pd.DataFrame) -> pd.DataFrame:
            return signals[["date", "symbol", "weight"]].copy()

    class _Executor:
        mode = "test"

        @staticmethod
        def execute(target, market, *, initial_cash=1_000_000.0, lot_size=100):
            pnl = pd.DataFrame(
                [
                    {
                        "date": "2024-01-03",
                        "signal_date": str(target["date"].iloc[0]),
                        "gross_return": 0.10,
                        "equity": initial_cash * 1.10,
                        "cum_return": 0.10,
                    }
                ]
            )
            return ExecutionRun(orders=pd.DataFrame(), holdings=pd.DataFrame(), pnl=pnl)

    strategies = [StrategySpec(name="s1", builder=lambda data: pd.DataFrame())]
    strategy_signals = pd.DataFrame(
        [
            {"date": "2024-01-02", "symbol": "000001", "weight": 1.0, "strategy": "s1", "score": 1.0},
        ]
    )

    result = PortfolioManager(initial_cash=1000.0, capital_caps={"s1": 0.4}).build(
        strategies=strategies,
        strategy_signals=strategy_signals,
        market=_build_synthetic_market(),
        allocator=_Allocator(),
        optimizer=_Optimizer(),
        executor=_Executor(),
    )

    row = result.aggregate_pnl.iloc[0]
    assert float(row["gross_return"]) == pytest.approx(0.04)
    assert float(row["cash_weight"]) == pytest.approx(0.6)
    assert float(row["cash_left"]) == pytest.approx(600.0)
    assert float(row["equity"]) == pytest.approx(1040.0)
    assert result.snapshot["cash_left"] == pytest.approx(600.0)
    assert result.snapshot["allocated_cash"] == pytest.approx(400.0)


def test_build_backtest_report_summary_uses_daily_aggregation() -> None:
    frame = pd.DataFrame(
        [
            {"date": "2024-01-02", "symbol": "000001", "rank": 1, "score": 1.0, "weight": 0.6, "gross_return": 0.01, "equity": 101.0, "cum_return": 0.01},
            {"date": "2024-01-02", "symbol": "000002", "rank": 2, "score": 3.0, "weight": 0.4, "gross_return": 0.01, "equity": 101.0, "cum_return": 0.01},
            {"date": "2024-01-03", "symbol": "000001", "rank": 1, "score": 5.0, "weight": 1.0, "gross_return": 0.02, "equity": 103.0, "cum_return": 0.03},
        ]
    )

    report = build_report(frame, "backtest")
    summary = report[report["section"] == "summary"].iloc[0]

    assert int(summary["signal_count"]) == 3
    assert float(summary["avg_score"]) == 3.5
    assert float(summary["avg_weight"]) == 0.75
    assert float(summary["gross_return"]) == 0.02
    assert float(summary["equity"]) == 103.0
    assert float(summary["cum_return"]) == 0.03


def test_build_backtest_report_preserves_multiple_signal_dates_in_daily_section() -> None:
    frame = pd.DataFrame(
        [
            {"date": "2024-01-03", "signal_date": "2024-01-02 09:35:00", "symbol": "000001", "rank": 1, "score": 1.0, "weight": 0.5, "gross_return": 0.01, "equity": 102.01, "cum_return": 0.0201},
            {"date": "2024-01-03", "signal_date": "2024-01-02 14:55:00", "symbol": "000002", "rank": 2, "score": 1.0, "weight": 0.5, "gross_return": 0.01, "equity": 102.01, "cum_return": 0.0201},
        ]
    )

    report = build_report(frame, "backtest")
    daily = report[report["section"] == "daily"].iloc[0]

    assert daily["signal_date"] == "2024-01-02 09:35:00 | 2024-01-02 14:55:00"
    assert float(daily["gross_return"]) == pytest.approx(0.02)


def test_daily_pnl_view_collapses_multi_signal_date_rows_to_daily_metrics() -> None:
    frame = pd.DataFrame(
        [
            {"date": "2024-01-03", "signal_date": "2024-01-02 09:35:00", "gross_return": 0.01, "equity": 1010.0, "cum_return": 0.01, "annualized_return": 11.0},
            {"date": "2024-01-03", "signal_date": "2024-01-02 14:55:00", "gross_return": 0.02, "equity": 1010.0, "cum_return": 0.01, "annualized_return": 11.0},
        ]
    )

    daily = daily_pnl_view(frame)

    assert len(daily) == 1
    assert float(daily.iloc[0]["gross_return"]) == pytest.approx(0.03)
    assert float(daily.iloc[0]["equity"]) == pytest.approx(1010.0)


def test_configure_logging_replaces_previous_file_handler(tmp_path: Path) -> None:
    logging_utils._CONFIGURED = False
    logging_utils._STDERR_HANDLER_ID = None
    logging_utils._FILE_HANDLER_ID = None

    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_log = logging_utils.configure_logging("first", first_dir)
    logging_utils.logger.info("first only")
    second_log = logging_utils.configure_logging("second", second_dir)
    logging_utils.logger.info("second only")

    first_text = first_log.read_text(encoding="utf-8")
    second_text = second_log.read_text(encoding="utf-8")

    assert "second only" not in first_text
    assert "second only" in second_text


def test_allocate_capital_uses_latest_trading_day_only() -> None:
    signals = pd.DataFrame(
        [
            {"date": "2024-01-02", "strategy": "s1", "score": 100.0},
            {"date": "2024-01-02", "strategy": "s2", "score": 1.0},
            {"date": "2024-01-03 09:35:00", "strategy": "s1", "score": 1.0},
            {"date": "2024-01-03 09:35:00", "strategy": "s2", "score": 3.0},
            {"date": "2024-01-03 14:55:00", "strategy": "s1", "score": 3.0},
            {"date": "2024-01-03 14:55:00", "strategy": "s2", "score": 1.0},
        ]
    )

    result = score_allocate_capital(signals, total_cash=400.0)
    alloc = result.allocation.set_index("strategy")["allocated_cash"].to_dict()

    assert alloc["s1"] == 200.0
    assert alloc["s2"] == 200.0


def test_allocate_capital_respects_caps_after_redistribution() -> None:
    signals = pd.DataFrame(
        [
            {"date": "2024-01-03", "strategy": "s1", "score": 9.0},
            {"date": "2024-01-03", "strategy": "s2", "score": 1.0},
        ]
    )

    result = score_allocate_capital(signals, total_cash=1000.0, caps={"s1": 0.4})
    alloc = result.allocation.set_index("strategy")["allocated_cash"].to_dict()

    assert alloc["s1"] == 400.0
    assert alloc["s2"] == 600.0
    assert result.cash_left == 0.0


def test_build_allocators_registers_all_supported_modes() -> None:
    allocators = build_allocators()

    assert {"score", "equal", "risk_parity", "optimized"}.issubset(allocators.keys())


def test_equal_allocator_splits_capital_evenly_across_strategies() -> None:
    signals = pd.DataFrame(
        [
            {"date": "2024-01-03", "strategy": "s1", "symbol": "000001", "score": 10.0, "weight": 0.5, "volatility": 0.03},
            {"date": "2024-01-03", "strategy": "s1", "symbol": "000002", "score": 1.0, "weight": 0.5, "volatility": 0.05},
            {"date": "2024-01-03", "strategy": "s2", "symbol": "000003", "score": 2.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-03", "strategy": "s3", "symbol": "000004", "score": 0.5, "weight": 1.0, "volatility": 0.01},
        ]
    )

    result = Allocator(mode="equal").allocate(signals, total_cash=900.0)
    alloc = result.allocation.set_index("strategy")["allocated_cash"].to_dict()

    assert alloc == {"s1": 300.0, "s2": 300.0, "s3": 300.0}
    assert result.cash_left == 0.0


def test_risk_parity_allocator_overweights_lower_volatility_strategy() -> None:
    signals = pd.DataFrame(
        [
            {"date": "2024-01-03", "strategy": "high_vol", "symbol": "000001", "score": 3.0, "weight": 1.0, "volatility": 0.04},
            {"date": "2024-01-03", "strategy": "mid_vol", "symbol": "000002", "score": 2.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-03", "strategy": "low_vol", "symbol": "000003", "score": 1.0, "weight": 1.0, "volatility": 0.01},
        ]
    )

    result = Allocator(mode="risk_parity").allocate(signals, total_cash=700.0)
    alloc = result.allocation.set_index("strategy")["allocated_cash"]

    assert alloc["low_vol"] > alloc["mid_vol"] > alloc["high_vol"]
    assert result.cash_left == 0.0


def test_optimized_allocator_respects_caps_with_score_risk_tradeoff() -> None:
    signals = pd.DataFrame(
        [
            {"date": "2024-01-03", "strategy": "s1", "symbol": "000001", "score": 6.0, "weight": 1.0, "volatility": 0.04},
            {"date": "2024-01-03", "strategy": "s2", "symbol": "000002", "score": 3.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-03", "strategy": "s3", "symbol": "000003", "score": 1.0, "weight": 1.0, "volatility": 0.01},
        ]
    )

    result = Allocator(mode="optimized").allocate(signals, total_cash=1_000.0, caps={"s1": 0.4})
    alloc = result.allocation.set_index("strategy")["allocated_cash"]

    assert float(alloc["s1"]) <= 400.0 + 1e-6
    assert float(alloc.sum()) <= 1_000.0 + 1e-6
    assert result.cash_left >= 0.0


def test_equal_allocator_ignores_score_magnitude() -> None:
    signals = pd.DataFrame(
        [
            {"date": "2024-01-03", "strategy": "s1", "symbol": "000001", "score": 100.0, "weight": 1.0, "volatility": 0.03},
            {"date": "2024-01-03", "strategy": "s2", "symbol": "000002", "score": 1.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-03", "strategy": "s3", "symbol": "000003", "score": 0.1, "weight": 1.0, "volatility": 0.01},
        ]
    )

    result = Allocator(mode="equal").allocate(signals, total_cash=900.0)
    weights = (result.allocation.set_index("strategy")["allocated_cash"] / 900.0).to_dict()

    assert weights == {"s1": pytest.approx(1 / 3), "s2": pytest.approx(1 / 3), "s3": pytest.approx(1 / 3)}
    assert result.cash_left == 0.0


def test_risk_parity_allocator_balances_diagonal_risk_contributions() -> None:
    signals = pd.DataFrame(
        [
            {"date": "2024-01-03", "strategy": "s1", "symbol": "000001", "score": 1.0, "weight": 1.0, "volatility": 0.04},
            {"date": "2024-01-03", "strategy": "s2", "symbol": "000002", "score": 1.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-03", "strategy": "s3", "symbol": "000003", "score": 1.0, "weight": 1.0, "volatility": 0.01},
        ]
    )

    result = Allocator(mode="risk_parity").allocate(signals, total_cash=1_000.0)
    weights = result.allocation.set_index("strategy")["allocated_cash"] / 1_000.0
    stats = aggregate_strategy_statistics(signals)
    covariance = diagonal_covariance_from_volatility(stats)
    contributions = risk_contributions(weights.sort_index(), covariance)

    assert weights["s3"] > weights["s2"] > weights["s1"]
    assert contributions.max() - contributions.min() < 1e-3


def test_optimized_allocator_falls_back_to_equal_when_scores_are_zero() -> None:
    signals = pd.DataFrame(
        [
            {"date": "2024-01-03", "strategy": "s1", "symbol": "000001", "score": 0.0, "weight": 1.0, "volatility": 0.04},
            {"date": "2024-01-03", "strategy": "s2", "symbol": "000002", "score": 0.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-03", "strategy": "s3", "symbol": "000003", "score": 0.0, "weight": 1.0, "volatility": 0.01},
        ]
    )

    result = Allocator(mode="optimized").allocate(signals, total_cash=900.0)
    alloc = result.allocation.set_index("strategy")["allocated_cash"].to_dict()

    assert alloc == {"s1": 300.0, "s2": 300.0, "s3": 300.0}
    assert result.cash_left == 0.0


def test_risk_parity_allocator_fills_missing_volatility_with_sample_median() -> None:
    signals = pd.DataFrame(
        [
            {"date": "2024-01-03", "strategy": "s1", "symbol": "000001", "score": 1.0, "weight": 1.0, "volatility": 0.03},
            {"date": "2024-01-03", "strategy": "s2", "symbol": "000002", "score": 1.0, "weight": 1.0, "volatility": None},
            {"date": "2024-01-03", "strategy": "s3", "symbol": "000003", "score": 1.0, "weight": 1.0, "volatility": 0.01},
        ]
    )

    result = Allocator(mode="risk_parity").allocate(signals, total_cash=900.0)
    alloc = result.allocation.set_index("strategy")["allocated_cash"]

    assert float(alloc.sum()) == pytest.approx(900.0)
    assert (alloc > 0).all()


def test_build_strategy_return_history_uses_next_day_weighted_returns() -> None:
    dates = pd.bdate_range("2024-01-02", periods=4)
    close = pd.DataFrame(
        {
            "a": [100.0, 110.0, 121.0, 133.1],
            "b": [100.0, 90.0, 81.0, 72.9],
        },
        index=dates,
    )
    market = _build_allocator_market(close)
    signals = pd.DataFrame(
        [
            {"date": "2024-01-02", "strategy": "s1", "symbol": "a", "score": 1.0, "weight": 0.75},
            {"date": "2024-01-02", "strategy": "s1", "symbol": "b", "score": 1.0, "weight": 0.25},
            {"date": "2024-01-02", "strategy": "s2", "symbol": "b", "score": 1.0, "weight": 1.0},
        ]
    )

    history = build_strategy_return_history(signals, market).set_index("date")

    assert float(history.loc[pd.Timestamp("2024-01-02"), "s1"]) == pytest.approx(0.05)
    assert float(history.loc[pd.Timestamp("2024-01-02"), "s2"]) == pytest.approx(-0.10)


def test_risk_parity_allocator_uses_history_context_when_available() -> None:
    dates = pd.bdate_range("2024-01-02", periods=4)
    close = pd.DataFrame(
        {
            "a": [100.0, 120.0, 96.0, 115.2],
            "b": [100.0, 101.0, 102.01, 103.0301],
        },
        index=dates,
    )
    market = _build_allocator_market(close)
    signals = pd.DataFrame(
        [
            {"date": "2024-01-02", "strategy": "s1", "symbol": "a", "score": 1.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-03", "strategy": "s1", "symbol": "a", "score": 1.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-04", "strategy": "s1", "symbol": "a", "score": 1.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-02", "strategy": "s2", "symbol": "b", "score": 1.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-03", "strategy": "s2", "symbol": "b", "score": 1.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-04", "strategy": "s2", "symbol": "b", "score": 1.0, "weight": 1.0, "volatility": 0.02},
        ]
    )

    no_context = Allocator(mode="risk_parity").allocate(signals, total_cash=900.0)
    with_context = Allocator(mode="risk_parity").allocate(
        signals,
        total_cash=900.0,
        context=AllocationContext(market=market),
    )
    no_context_alloc = no_context.allocation.set_index("strategy")["allocated_cash"]
    with_context_alloc = with_context.allocation.set_index("strategy")["allocated_cash"]

    assert float(no_context_alloc["s1"]) == pytest.approx(float(no_context_alloc["s2"]))
    assert float(with_context_alloc["s2"]) > float(with_context_alloc["s1"])


def test_optimized_allocator_uses_history_context_when_available() -> None:
    dates = pd.bdate_range("2024-01-02", periods=4)
    close = pd.DataFrame(
        {
            "a": [100.0, 103.0, 106.09, 109.2727],
            "b": [100.0, 99.0, 98.01, 97.0299],
        },
        index=dates,
    )
    market = _build_allocator_market(close)
    signals = pd.DataFrame(
        [
            {"date": "2024-01-02", "strategy": "s1", "symbol": "a", "score": 1.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-03", "strategy": "s1", "symbol": "a", "score": 1.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-04", "strategy": "s1", "symbol": "a", "score": 1.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-02", "strategy": "s2", "symbol": "b", "score": 1.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-03", "strategy": "s2", "symbol": "b", "score": 1.0, "weight": 1.0, "volatility": 0.02},
            {"date": "2024-01-04", "strategy": "s2", "symbol": "b", "score": 1.0, "weight": 1.0, "volatility": 0.02},
        ]
    )

    no_context = Allocator(mode="optimized").allocate(signals, total_cash=900.0)
    with_context = Allocator(mode="optimized").allocate(
        signals,
        total_cash=900.0,
        context=AllocationContext(market=market),
    )
    no_context_alloc = no_context.allocation.set_index("strategy")["allocated_cash"]
    with_context_alloc = with_context.allocation.set_index("strategy")["allocated_cash"]

    assert float(no_context_alloc["s1"]) == pytest.approx(float(no_context_alloc["s2"]))
    assert float(with_context_alloc["s1"]) > float(with_context_alloc["s2"])


def test_signal_generator_validates_strategy_output() -> None:
    generator = SignalGenerator(
        strategies=[
            StrategySpec(
                name="broken",
                builder=lambda data: pd.DataFrame([{"date": "2024-01-02", "symbol": "000001", "weight": -1.0}]),
            )
        ]
    )

    with pytest.raises(ValueError, match="策略输出不合法"):
        generator.generate(_build_synthetic_market())


def test_signal_generator_rejects_incomplete_signal_schema() -> None:
    generator = SignalGenerator(
        strategies=[
            StrategySpec(
                name="broken",
                builder=lambda data: pd.DataFrame([{"date": "2024-01-02", "symbol": "000001", "weight": 1.0}]),
            )
        ]
    )

    with pytest.raises(ValueError, match="缺少字段：rank, score"):
        generator.generate(_build_synthetic_market())


def test_normalize_signal_frame_preserves_intraday_time_granularity() -> None:
    frame = pd.DataFrame(
        [
            {"date": "2024-01-02 09:35:00", "symbol": "000001", "rank": 1, "score": 1.0, "weight": 1.0},
            {"date": "2024-01-02", "symbol": "000002", "rank": 1, "score": 2.0, "weight": 1.0},
        ]
    )

    normalized = normalize_signal_frame(frame)

    assert normalized.iloc[0]["date"] == "2024-01-02"
    assert normalized.iloc[1]["date"] == "2024-01-02 09:35:00"


def test_latest_signal_frame_keeps_all_rows_from_latest_trading_day() -> None:
    frame = pd.DataFrame(
        [
            {"date": "2024-01-02 14:50:00", "symbol": "000001", "rank": 1, "score": 1.0, "weight": 1.0},
            {"date": "2024-01-03 09:35:00", "symbol": "000002", "rank": 1, "score": 2.0, "weight": 0.5},
            {"date": "2024-01-03 14:55:00", "symbol": "000003", "rank": 2, "score": 1.5, "weight": 0.5},
        ]
    )

    latest = latest_signal_frame(frame)

    assert latest["date"].tolist() == ["2024-01-03 09:35:00", "2024-01-03 14:55:00"]


def test_report_input_for_backtest_preserves_intraday_metric_alignment() -> None:
    signals = pd.DataFrame(
        [
            {"date": "2024-01-03 09:35:00", "symbol": "000001", "rank": 1, "score": 1.0, "weight": 1.0},
        ]
    )
    pnl = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2024-01-04 09:35:00"),
                "signal_date": pd.Timestamp("2024-01-03 09:35:00"),
                "gross_return": 0.01,
                "equity": 101.0,
                "cum_return": 0.01,
            },
        ]
    )

    merged = _report_input_for_backtest(signals, pnl)

    assert float(merged.iloc[0]["gross_return"]) == 0.01
    assert float(merged.iloc[0]["equity"]) == 101.0
    assert float(merged.iloc[0]["cum_return"]) == 0.01


def test_optimizer_rejects_missing_volatility_for_inv_vol() -> None:
    signals = pd.DataFrame(
        [
            {"date": "2024-01-03", "symbol": "000001", "score": 1.0, "weight": 1.0},
        ]
    )

    with pytest.raises(ValueError, match="优化器需要 volatility 列: inv_vol"):
        Optimizer(mode="inv_vol").optimize(signals)


def test_optimizer_rejects_missing_volatility_for_blend() -> None:
    signals = pd.DataFrame(
        [
            {"date": "2024-01-03", "symbol": "000001", "score": 1.0, "weight": 1.0},
        ]
    )

    with pytest.raises(ValueError, match="优化器需要 volatility 列: blend"):
        Optimizer(mode="blend").optimize(signals)


def test_apply_overrides_normalizes_cli_aliases() -> None:
    config = default_qts_config()

    updated = apply_overrides(config, allocation_mode="风险平价", optimizer_mode="混合", execution_mode="回测")

    assert updated.system.allocation_mode == "risk_parity"
    assert updated.system.optimizer_mode == "blend"
    assert updated.system.execution_mode == "backtest"


def test_package_root_exports_runtime_entrypoints() -> None:
    import qts
    from qts import data_source

    assert data_source is qts.data_source
    assert qts.DEFAULT_SYMBOL == "000001"
    assert callable(qts.load_market_panel)
    assert qts.MultiDecisionSystem.__name__ == "MultiDecisionSystem"
