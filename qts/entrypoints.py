from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import QTSConfig, build_system_from_config, load_market_from_config, load_qts_config
from .engine import SystemRunResult
from .models import MarketPanel
from .report import build_report, latest_signal_frame, normalize_signal_frame

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "configs"
DEFAULT_BACKTEST_CONFIG = CONFIG_DIR / "backtest.json"
DEFAULT_CLOSE_REPORT_CONFIG = CONFIG_DIR / "close_report.json"
DEFAULT_STOCK_SELECTION_CONFIG = CONFIG_DIR / "stock_selection.json"


@dataclass(frozen=True)
class EntryRun:
    """保存单入口运行结果。"""

    name: str
    config_path: Path | None
    config: QTSConfig
    market: MarketPanel
    result: SystemRunResult
    signals: pd.DataFrame
    report: pd.DataFrame


def resolve_entry_config_path(default_path: Path, config_path: str | Path | None = None) -> Path | None:
    """解析入口使用的配置路径。"""
    if config_path is not None:
        return Path(config_path)
    if default_path.exists():
        return default_path
    nested_default = REPO_ROOT / "configs" / default_path.name
    if nested_default.exists():
        return nested_default
    return None


def _load_config(default_path: Path, config_path: str | Path | None = None) -> tuple[Path | None, QTSConfig]:
    """加载入口配置。"""
    resolved = resolve_entry_config_path(default_path, config_path)
    config = load_qts_config(resolved)
    return resolved, config


def _run_entry(
    *,
    name: str,
    default_path: Path,
    config_path: str | Path | None = None,
    cache_root: Path | None = None,
    report_kind: str,
    latest_only: bool = False,
) -> EntryRun:
    """运行指定入口并生成报表。"""
    resolved, config = _load_config(default_path, config_path)
    market = load_market_from_config(config, cache_root=cache_root)
    system = build_system_from_config(config)
    result = system.run(market)
    signals = latest_signal_frame(result.strategy_signals) if latest_only else normalize_signal_frame(result.strategy_signals)
    report_input = signals.copy()
    if not result.aggregate_pnl.empty and report_kind == "backtest":
        pnl = result.aggregate_pnl.copy()
        pnl["date"] = pd.to_datetime(pnl["date"]).dt.strftime("%Y-%m-%d")
        keep_columns = [column for column in ["date", "gross_return", "equity", "cum_return"] if column in pnl.columns]
        if keep_columns:
            report_input = report_input.merge(pnl[keep_columns], on="date", how="left")
    report = build_report(report_input, report_kind)
    return EntryRun(name, resolved, config, market, result, signals, report)


def run_backtest_entry(
    config_path: str | Path | None = None,
    *,
    cache_root: Path | None = None,
) -> EntryRun:
    """运行回测入口。"""
    return _run_entry(
        name="backtest",
        default_path=DEFAULT_BACKTEST_CONFIG,
        config_path=config_path,
        cache_root=cache_root,
        report_kind="backtest",
    )


def run_close_report_entry(
    config_path: str | Path | None = None,
    *,
    cache_root: Path | None = None,
) -> EntryRun:
    """运行收盘决策入口。"""
    return _run_entry(
        name="close_report",
        default_path=DEFAULT_CLOSE_REPORT_CONFIG,
        config_path=config_path,
        cache_root=cache_root,
        report_kind="close",
        latest_only=True,
    )


def run_stock_selection_entry(
    config_path: str | Path | None = None,
    *,
    cache_root: Path | None = None,
) -> EntryRun:
    """运行选股入口。"""
    return _run_entry(
        name="stock_selection",
        default_path=DEFAULT_STOCK_SELECTION_CONFIG,
        config_path=config_path,
        cache_root=cache_root,
        report_kind="selection",
        latest_only=True,
    )
