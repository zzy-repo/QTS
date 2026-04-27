from __future__ import annotations

from _bootstrap import ROOT
from qts.entrypoints import DEFAULT_CLOSE_REPORT_CONFIG, run_close_report_entry

from _entry_common import save_frame, save_text


def run_close_report_script() -> None:
    artifact_dir = ROOT / "artifacts" / "close_report"
    run = run_close_report_entry(cache_root=artifact_dir / "cache")
    save_frame(run.signals, artifact_dir / "signals.csv")
    save_frame(run.report, artifact_dir / "report.csv")
    save_text(f"配置：{run.config_path or DEFAULT_CLOSE_REPORT_CONFIG}\n状态：完成\n", artifact_dir / "run.txt")
    print("收盘决策入口已完成")


if __name__ == "__main__":
    run_close_report_script()
