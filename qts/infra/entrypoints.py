from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger

from ..core.data.data_source import describe_source_mode
from ..paths import REPO_ROOT
from .config import QTSConfig, build_system_from_config, load_market_from_config, load_qts_config
from .models import EntryRun
from .report import build_report, latest_signal_frame, normalize_signal_frame

CONFIG_DIR = REPO_ROOT / "configs"
DEFAULT_BACKTEST_CONFIG = CONFIG_DIR / "backtest.json"
DEFAULT_CLOSE_REPORT_CONFIG = CONFIG_DIR / "close_report.json"
DEFAULT_STOCK_SELECTION_CONFIG = CONFIG_DIR / "stock_selection.json"


def resolve_entry_config_path(default_path: Path, config_path: str | Path | None = None) -> Path | None:
    """解析入口使用的配置路径。"""
    if config_path is not None:
        return Path(config_path)
    if default_path.exists():
        return default_path
    return None


def _load_config(default_path: Path, config_path: str | Path | None = None) -> tuple[Path | None, QTSConfig]:
    """加载入口配置。"""
    resolved = resolve_entry_config_path(default_path, config_path)
    config = load_qts_config(resolved)
    logger.info("配置已加载 路径={} 标的={} 开始={} 结束={}", resolved, config.market.symbols, config.market.start_date, config.market.end_date)
    return resolved, config


def _signal_frame_for_report(result, *, latest_only: bool) -> pd.DataFrame:
    """按入口类型选择要输出的信号粒度。"""
    if latest_only:
        return latest_signal_frame(result.strategy_signals)
    return normalize_signal_frame(result.strategy_signals)


def _report_input_for_backtest(signals: pd.DataFrame, aggregate_pnl: pd.DataFrame) -> pd.DataFrame:
    """把回测收益指标合并进报表输入。"""
    report_input = signals.copy()
    if aggregate_pnl.empty:
        return report_input

    report_input["_report_ts"] = pd.to_datetime(report_input["date"], format="mixed")
    pnl = aggregate_pnl.copy()
    report_key = "signal_date" if "signal_date" in pnl.columns else "date"
    pnl["_report_ts"] = pd.to_datetime(pnl[report_key], format="mixed")
    keep_columns = [column for column in ["_report_ts", "gross_return", "equity", "cum_return"] if column in pnl.columns]
    if keep_columns:
        report_input = report_input.merge(pnl[keep_columns], on="_report_ts", how="left")
    return report_input.drop(columns="_report_ts")


def _build_report_input(signals: pd.DataFrame, *, report_kind: str, aggregate_pnl: pd.DataFrame) -> pd.DataFrame:
    """生成报表输入数据。"""
    if report_kind == "backtest":
        return _report_input_for_backtest(signals, aggregate_pnl)
    return signals.copy()


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
    logger.info("入口启动 名称={} 配置路径={} 缓存目录={} 报表类型={} 仅最新信号={}", name, config_path, cache_root, report_kind, latest_only)
    resolved, config = _load_config(default_path, config_path)
    market = load_market_from_config(config, cache_root=cache_root)
    logger.info(
        "市场数据已加载 入口={} 数据来源={}({}) 行数={} 标的={}",
        name,
        describe_source_mode(market.source_mode),
        market.source_mode,
        len(market.close),
        list(market.close.columns),
    )
    system = build_system_from_config(config)
    result = system.run(market)
    logger.info(
        "系统运行完成 入口={} 策略运行数={} 收益行数={} 权益行数={}",
        name,
        len(result.strategy_runs),
        len(result.aggregate_pnl),
        len(result.aggregate_equity),
    )
    signals = _signal_frame_for_report(result, latest_only=latest_only)
    report_input = _build_report_input(signals, report_kind=report_kind, aggregate_pnl=result.aggregate_pnl)
    report = build_report(report_input, report_kind)
    logger.info(
        "报表已生成 入口={} 信号行数={} 报表行数={} 报表类型={}",
        name,
        len(signals),
        len(report),
        report_kind,
    )
    return EntryRun(
        name=name,
        config_path=resolved,
        config=config,
        market=market,
        result=result,
        signals=signals,
        report=report,
    )


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
