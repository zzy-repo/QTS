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
from qts.core.portfolio.allocation import allocate_capital
from qts.core.portfolio.results import annualized_return, daily_pnl_view
from qts.core.optimize.engine import Optimizer
from qts.core.signal.engine import SignalGenerator
from qts.core.signal.specs import StrategySpec
from qts.infra.config import apply_overrides, build_system_from_config, default_qts_config, load_qts_config, save_qts_config
from qts.infra.entrypoints import (
    DEFAULT_BACKTEST_CONFIG,
    _report_input_for_backtest,
    run_backtest_entry,
    run_close_report_entry,
    run_stock_selection_entry,
)
from qts.infra import cli as cli_module
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


def test_qts_config_round_trip(tmp_path: Path) -> None:
    config = default_qts_config()
    target = tmp_path / "qts.config.json"
    save_qts_config(config, target)

    loaded = load_qts_config(target)

    assert loaded.to_dict() == config.to_dict()


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


def test_default_backtest_config_points_to_repo_root() -> None:
    assert DEFAULT_BACKTEST_CONFIG == REPO_ROOT / "configs" / "backtest.json"


def test_default_market_cache_root_points_to_repo_root() -> None:
    assert cache_module.default_cache_root() == REPO_ROOT / ".cache" / "qts-market"


def test_entrypoints_use_latest_signals(monkeypatch) -> None:
    market = _build_synthetic_market()

    from qts.infra import entrypoints as entrypoints_module

    seen_cache_roots: list[Path | None] = []

    def fake_load_market_from_config(config, cache_root=None):
        seen_cache_roots.append(cache_root)
        return market

    monkeypatch.setattr(entrypoints_module, "load_market_from_config", fake_load_market_from_config)

    backtest_run = run_backtest_entry()
    close_run = run_close_report_entry()
    stock_run = run_stock_selection_entry()

    assert "signal_date" in backtest_run.result.aggregate_pnl.columns
    assert backtest_run.result.aggregate_pnl["annualized_return"].nunique(dropna=False) > 1
    aggregate_pnl = backtest_run.result.aggregate_pnl
    expected_annualized = annualized_return(float(aggregate_pnl["cum_return"].iloc[-1]), len(aggregate_pnl))
    assert float(aggregate_pnl["annualized_return"].iloc[-1]) == expected_annualized
    assert close_run.signals["date"].nunique() == 1
    assert stock_run.signals["date"].nunique() == 1
    assert "decision" in close_run.report.columns
    assert "selected" in stock_run.report.columns
    assert seen_cache_roots == [None, None, None]


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
        strategies=[StrategyConfig(name="sharpe", kind="sharpe", lookback=15, top_n=3)],
    )
    system = build_system_from_config(config)
    market = _build_synthetic_market()

    result = system.run(market)

    assert not result.aggregate_pnl.empty
    assert "performance" in result.snapshot
    assert result.snapshot["optimizer_mode"] == "blend"
    assert pd.isna(result.snapshot["performance"]["turnover"])


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
        optimizer=_Optimizer(),
        executor=executor,
    )

    assert executor.calls == [250.0, 750.0]
    assert [run.allocation_cash for run in result.strategy_runs] == [250.0, 750.0]


def test_portfolio_manager_preserves_multiple_signal_dates_for_same_realization_day() -> None:
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
        optimizer=_Optimizer(),
        executor=_Executor(),
    )

    assert result.aggregate_pnl["signal_date"].tolist() == ["2024-01-02 09:35:00", "2024-01-02 14:55:00"]
    assert result.aggregate_pnl["equity"].tolist() == [1010.0, 1010.0]
    assert result.aggregate_pnl["cum_return"].tolist() == pytest.approx([0.01, 0.01])


def test_portfolio_manager_exposes_cash_left_in_aggregate_semantics() -> None:
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

    result = allocate_capital(signals, total_cash=400.0)
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

    result = allocate_capital(signals, total_cash=1000.0, caps={"s1": 0.4})
    alloc = result.allocation.set_index("strategy")["allocated_cash"].to_dict()

    assert alloc["s1"] == 400.0
    assert alloc["s2"] == 600.0
    assert result.cash_left == 0.0


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


def test_signal_generator_rejects_legacy_signal_schema() -> None:
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


def test_cli_optimizer_labels_cover_supported_modes() -> None:
    assert cli_module._OPTIMIZER_LABELS["inv_vol"] == "逆波动率"
    assert cli_module._OPTIMIZER_LABELS["blend"] == "混合"


def test_apply_overrides_normalizes_cli_aliases() -> None:
    config = default_qts_config()

    updated = apply_overrides(config, optimizer_mode="混合", execution_mode="回测")

    assert updated.system.optimizer_mode == "blend"
    assert updated.system.execution_mode == "backtest"


def test_package_root_preserves_compatibility_exports() -> None:
    import qts
    from qts import data_source

    assert data_source is qts.data_source
    assert qts.DEFAULT_SYMBOL == "000001"
    assert callable(qts.load_market_panel)
    assert qts.MultiDecisionSystem.__name__ == "MultiDecisionSystem"
