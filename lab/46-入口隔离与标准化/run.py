from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json

import pandas as pd

from bootstrap import ROOT
from entry_helpers import (
    EntryRun,
    default_artifact_dir,
    fake_fetch_daily_history,
    load_market_panel_with_cache,
    save_frame,
)
from report import build_report
from shared import ExperimentMeta, record_experiment

from run_backtest import run as run_backtest
from run_close_report import run as run_close_report
from run_stock_selection import run as run_stock_selection


def _memory_cache_probe() -> dict[str, object]:
    cache_store: dict[Path, pd.DataFrame] = {}
    cache_root = default_artifact_dir() / "cache-smoke"
    cache_root.mkdir(parents=True, exist_ok=True)

    def read_cache(path: Path) -> pd.DataFrame:
        frame = cache_store.get(path)
        if frame is None:
            return pd.DataFrame(columns=["date", "symbol", "close", "volume", "amount"])
        return frame.copy()

    def write_cache(frame: pd.DataFrame, path: Path) -> None:
        cache_store[path] = frame.copy()

    from qts.data_source import sync_symbol_history

    first = sync_symbol_history(
        "000001",
        "20240102",
        "20240115",
        cache_root=cache_root,
        fetcher=fake_fetch_daily_history,
        read_cache=read_cache,
        write_cache=write_cache,
    )
    second = sync_symbol_history(
        "000001",
        "20240102",
        "20240115",
        cache_root=cache_root,
        fetcher=fake_fetch_daily_history,
        read_cache=read_cache,
        write_cache=write_cache,
    )
    return {
        "first_cache_hit": first.cache_hit,
        "first_network_hit": first.network_hit,
        "second_cache_hit": second.cache_hit,
        "second_network_hit": second.network_hit,
        "frames_equal": bool(first.frame.equals(second.frame)),
        "fetched_ranges_first": first.fetched_ranges,
        "fetched_ranges_second": second.fetched_ranges,
        "state_path": str(first.state_path),
    }


def _summarize_entry(run: EntryRun) -> dict[str, object]:
    return {
        "name": run.name,
        "config_path": str(run.config_path),
        "market_source_mode": run.market.source_mode,
        "signal_rows": int(len(run.signals)),
        "report_rows": int(len(run.report)),
        "report_columns": list(run.report.columns),
    }


def main() -> None:
    meta = ExperimentMeta(
        code="46",
        title="入口隔离与标准化",
        goal="验证同一核心模块可被不同入口复用，且输出格式、配置和缓存接口可以统一。",
        root=ROOT,
    )

    artifact_dir = default_artifact_dir()

    backtest = run_backtest()
    close_report = run_close_report()
    selection = run_stock_selection()
    cache_probe = _memory_cache_probe()

    summaries = pd.DataFrame([_summarize_entry(run) for run in (backtest, close_report, selection)])
    save_frame(summaries, artifact_dir / "entry_summary.csv")
    save_frame(backtest.result.aggregate_pnl, artifact_dir / "backtest_pnl.csv")
    save_frame(backtest.report, artifact_dir / "backtest_report.csv")
    save_frame(close_report.report, artifact_dir / "close_report.csv")
    save_frame(selection.report, artifact_dir / "selection_report.csv")
    (artifact_dir / "cache_probe.json").write_text(json.dumps(cache_probe, ensure_ascii=False, indent=2), encoding="utf-8")

    schema_ok = all(list(run.signals.columns)[:5] == ["date", "symbol", "rank", "score", "weight"] for run in (backtest, close_report, selection))
    isolated_ok = len({str(run.config_path) for run in (backtest, close_report, selection)}) == 3
    report_ok = all(not run.report.empty for run in (backtest, close_report, selection))
    cache_ok = (
        cache_probe["first_network_hit"] is True
        and cache_probe["second_cache_hit"] is True
        and cache_probe["second_network_hit"] is False
        and cache_probe["frames_equal"] is True
    )
    config_diff_ok = (
        backtest.config.system.execution_mode != close_report.config.system.execution_mode
        and backtest.config.strategies[0].lookback != close_report.config.strategies[0].lookback
        and selection.config.strategies[0].top_n != backtest.config.strategies[0].top_n
    )

    status = "pass" if schema_ok and isolated_ok and report_ok and cache_ok and config_diff_ok else "fail"
    steps = [
        "三个最小入口分别调用同一套 qts.config、qts.engine、qts.data_source。",
        "统一把信号整理成 date/symbol/rank/score/weight 五列，再交给 report.py。",
        "用独立配置文件区分回测、收盘决策和选股参数。",
        "用 sync_symbol_history 的自定义缓存回调验证首次拉取与二次命中复用。",
    ]
    artifacts = [
        "artifacts/backtest_signals.csv",
        "artifacts/backtest_pnl.csv",
        "artifacts/backtest_report.csv",
        "artifacts/close_signals.csv",
        "artifacts/close_report.csv",
        "artifacts/selection_signals.csv",
        "artifacts/selection_report.csv",
        "artifacts/entry_summary.csv",
        "artifacts/cache_probe.json",
    ]
    conclusion = "入口可以隔离，信号可以标准化，配置和缓存也能按入口独立复用。" if status == "pass" else "入口隔离、信号标准化或缓存复用至少一项未通过。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()

