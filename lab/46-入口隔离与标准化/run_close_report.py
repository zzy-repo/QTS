from __future__ import annotations

from pathlib import Path
import argparse
import json

from entry_helpers import (
    EntryRun,
    default_artifact_dir,
    latest_signal_frame,
    run_configured_system,
    save_frame,
    save_json_payload,
    signals_to_json_ready,
)
from report import build_report

DEFAULT_CONFIG = "close_report_config.json"


def run(config_path: str | Path | None = None) -> EntryRun:
    artifact_dir = default_artifact_dir()
    cache_root = artifact_dir / "cache-close"
    resolved, config, market, result, signals = run_configured_system(config_path, DEFAULT_CONFIG, cache_root=cache_root)
    latest = latest_signal_frame(signals)
    report = build_report(latest, "close")

    save_frame(signals, artifact_dir / "close_signals.csv")
    save_frame(report, artifact_dir / "close_report.csv")
    save_json_payload(signals_to_json_ready(signals), artifact_dir / "close_signals.json")
    save_json_payload(json.loads(report.where(report.notna(), None).to_json(orient="records", force_ascii=False)), artifact_dir / "close_report.json")

    return EntryRun(
        name="close_report",
        config_path=resolved,
        config=config,
        market=market,
        result=result,
        signals=signals,
        report=report,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="实验 46 收盘决策入口")
    parser.add_argument("--config", default=None, help="配置文件路径")
    args = parser.parse_args(argv)
    run(args.config)
    print("收盘决策入口已完成")


if __name__ == "__main__":
    main()
