from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import requests

from qts.core.data.models import MarketPanel
from qts.core.data import data_source as data_source_module
from qts.core.portfolio.results import annualized_return
from qts.infra.config import build_system_from_config, default_qts_config, load_qts_config, save_qts_config
from qts.infra.entrypoints import DEFAULT_BACKTEST_CONFIG, run_backtest_entry, run_close_report_entry, run_stock_selection_entry
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
    repo_root = Path(__file__).resolve().parents[1]
    assert DEFAULT_BACKTEST_CONFIG == repo_root / "configs" / "backtest.json"


def test_entrypoints_use_latest_signals(monkeypatch) -> None:
    market = _build_synthetic_market()

    from qts.infra import entrypoints as entrypoints_module

    monkeypatch.setattr(entrypoints_module, "load_market_from_config", lambda config, cache_root=None: market)

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


def test_load_market_panel_propagates_unexpected_errors(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(data_source_module, "sync_symbol_history", boom)

    with pytest.raises(RuntimeError, match="boom"):
        data_source_module.load_market_panel(["000001"], "20240102", "20240110")


def test_load_market_panel_falls_back_when_symbol_data_missing(monkeypatch) -> None:
    empty_sync = data_source_module.SyncResult(
        frame=pd.DataFrame(columns=["date", "symbol", "close", "volume", "amount"]),
        cache_frame=pd.DataFrame(columns=["date", "symbol", "close", "volume", "amount"]),
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
    assert float(frame.iloc[0]["volume"]) == 300.0
    assert float(frame.iloc[0]["amount"]) == 3600.0
