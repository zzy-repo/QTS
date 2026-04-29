from __future__ import annotations

from pathlib import Path
import argparse
import json

from bootstrap import ROOT
from entry_helpers import (
    EntryRun,
    default_artifact_dir,
    enrich_with_pnl,
    run_configured_system,
    save_frame,
    save_json_payload,
    signals_to_json_ready,
)
from report import build_report

DEFAULT_CONFIG = "backtest_config.json"


def run(config_path: str | Path | None = None) -> EntryRun:
    artifact_dir = default_artifact_dir()
    cache_root = artifact_dir / "cache-backtest"
    resolved, config, market, result, signals = run_configured_system(config_path, DEFAULT_CONFIG, cache_root=cache_root)
    report_input = enrich_with_pnl(signals, result.aggregate_pnl)
    report = build_report(report_input, "backtest")

    save_frame(signals, artifact_dir / "backtest_signals.csv")
    save_frame(result.aggregate_pnl, artifact_dir / "backtest_pnl.csv")
    save_frame(report, artifact_dir / "backtest_report.csv")
    save_json_payload(signals_to_json_ready(signals), artifact_dir / "backtest_signals.json")
    save_json_payload(signals_to_json_ready(report_input), artifact_dir / "backtest_report_input.json")
    save_json_payload(json.loads(report.where(report.notna(), None).to_json(orient="records", force_ascii=False)), artifact_dir / "backtest_report.json")

    return EntryRun(
        name="backtest",
        config_path=resolved,
        config=config,
        market=market,
        result=result,
        signals=signals,
        report=report,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="实验 46 回测入口")
    parser.add_argument("--config", default=None, help="配置文件路径")
    args = parser.parse_args(argv)
    run(args.config)
    print("回测入口已完成")


if __name__ == "__main__":
    main()
