from __future__ import annotations

from _bootstrap import ROOT
from qts.entrypoints import DEFAULT_BACKTEST_CONFIG, run_backtest_entry

from _entry_common import save_frame, save_text


def run_backtest_script() -> None:
    artifact_dir = ROOT / "artifacts" / "backtest"
    run = run_backtest_entry(cache_root=artifact_dir / "cache")
    save_frame(run.signals, artifact_dir / "signals.csv")
    save_frame(run.result.aggregate_pnl, artifact_dir / "pnl.csv")
    save_frame(run.report, artifact_dir / "report.csv")
    save_text(f"配置：{run.config_path or DEFAULT_BACKTEST_CONFIG}\n状态：完成\n", artifact_dir / "run.txt")
    print("回测入口已完成")


if __name__ == "__main__":
    run_backtest_script()
