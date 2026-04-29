from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger

from ..core.data.data_source import describe_source_mode
from ..paths import REPO_ROOT
from .config import QTSConfig, load_market_from_config, load_qts_config
from .models import EntryRun
from .report import build_report, normalize_signal_frame

CONFIG_DIR = REPO_ROOT / "configs"
DEFAULT_ENTRY_CONFIG = CONFIG_DIR / "qts.config.json"


def _resolve_entry_config_path(config_path: str | Path | None = None) -> Path | None:
    """解析统一入口使用的配置路径。"""
    if config_path is not None:
        return Path(config_path)
    if DEFAULT_ENTRY_CONFIG.exists():
        return DEFAULT_ENTRY_CONFIG
    return None


def _load_config(config_path: str | Path | None = None) -> tuple[Path | None, QTSConfig]:
    """加载统一入口配置。"""
    resolved = _resolve_entry_config_path(config_path)
    config = load_qts_config(resolved)
    logger.info(
        "配置已加载 路径={} 入口={} 报表类型={} 标的={} 开始={} 结束={}",
        resolved,
        config.entry.name,
        config.entry.report_kind,
        config.market.symbols,
        config.market.start_date,
        config.market.end_date,
    )
    return resolved, config


def _run_loaded_config(
    config: QTSConfig,
    *,
    config_path: Path | None,
    cache_root: Path | None = None,
) -> EntryRun:
    """运行已加载的统一入口配置。"""
    logger.info("入口启动 配置路径={} 缓存目录={}", config_path, cache_root)
    market = load_market_from_config(config, cache_root=cache_root)
    logger.info(
        "市场数据已加载 入口={} 数据来源={}({}) 行数={} 标的={}",
        config.entry.name,
        describe_source_mode(market.source_mode),
        market.source_mode,
        len(market.close),
        list(market.close.columns),
    )
    from .config import build_system_from_config

    system = build_system_from_config(config)
    result = system.run(market)
    logger.info(
        "系统运行完成 入口={} 策略运行数={} 收益行数={} 权益行数={}",
        config.entry.name,
        len(result.strategy_runs),
        len(result.aggregate_pnl),
        len(result.aggregate_equity),
    )
    signals = normalize_signal_frame(result.strategy_signals)
    report_input = _build_report_input(signals, report_kind=config.entry.report_kind, aggregate_pnl=result.aggregate_pnl)
    report = build_report(report_input, config.entry.report_kind)
    artifact_dir = resolve_artifact_dir(config)
    logger.info(
        "报表已生成 入口={} 信号行数={} 报表行数={} 报表类型={} 输出目录={}",
        config.entry.name,
        len(signals),
        len(report),
        config.entry.report_kind,
        artifact_dir,
    )
    return EntryRun(
        name=config.entry.name,
        config_path=config_path,
        artifact_dir=artifact_dir,
        outputs=list(config.entry.outputs),
        config=config,
        market=market,
        result=result,
        signals=signals,
        report=report,
    )


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


def resolve_artifact_dir(config: QTSConfig) -> Path:
    """把配置中的输出目录解析为仓库内绝对路径。"""
    artifact_dir = Path(config.entry.artifact_dir)
    if artifact_dir.is_absolute():
        return artifact_dir
    return REPO_ROOT / artifact_dir


def _build_run_summary(run: EntryRun) -> str:
    """生成入口运行摘要。"""
    return (
        f"配置：{run.config_path or DEFAULT_ENTRY_CONFIG}\n"
        f"入口：{run.name}\n"
        f"状态：完成\n"
        f"报表类型：{run.config.entry.report_kind}\n"
        f"数据来源：{describe_source_mode(run.market.source_mode)} ({run.market.source_mode})\n"
    )


def save_frame(frame: pd.DataFrame, path: Path) -> None:
    """保存数据表到 CSV。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    logger.info("saved frame path={} rows={} columns={}", path, len(frame), list(frame.columns))


def save_text(text: str, path: Path) -> None:
    """保存文本文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    logger.info("saved text path={} bytes={}", path, len(text.encode("utf-8")))


def _save_entry_artifacts(run: EntryRun) -> None:
    """按配置写出入口产物。"""
    writers = {
        "signals": lambda: save_frame(run.signals, run.artifact_dir / "signals.csv"),
        "report": lambda: save_frame(run.report, run.artifact_dir / "report.csv"),
        "pnl": lambda: save_frame(run.result.aggregate_pnl, run.artifact_dir / "pnl.csv"),
        "run_summary": lambda: save_text(_build_run_summary(run), run.artifact_dir / "run.txt"),
    }
    for output in run.outputs:
        writer = writers.get(output)
        if writer is None:
            logger.warning("忽略未知输出类型 output={}", output)
            continue
        writer()


def run_entry(
    config_path: str | Path | None = None,
    *,
    cache_root: Path | None = None,
) -> EntryRun:
    """运行统一入口并生成报表。"""
    resolved, config = _load_config(config_path)
    return _run_loaded_config(config, config_path=resolved, cache_root=cache_root)
