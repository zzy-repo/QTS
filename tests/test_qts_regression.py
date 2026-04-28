from __future__ import annotations

from pathlib import Path

import pandas as pd

from qts.core.data.models import MarketPanel
from qts.infra.config import build_system_from_config, default_qts_config, load_qts_config, save_qts_config
from qts.infra.entrypoints import run_close_report_entry, run_stock_selection_entry


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


def test_entrypoints_use_latest_signals(monkeypatch) -> None:
    market = _build_synthetic_market()

    from qts.infra import entrypoints as entrypoints_module

    monkeypatch.setattr(entrypoints_module, "load_market_from_config", lambda config, cache_root=None: market)

    close_run = run_close_report_entry()
    stock_run = run_stock_selection_entry()

    assert close_run.signals["date"].nunique() == 1
    assert stock_run.signals["date"].nunique() == 1
    assert "decision" in close_run.report.columns
    assert "selected" in stock_run.report.columns
