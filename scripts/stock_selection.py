from __future__ import annotations

from _bootstrap import ROOT
from qts.entrypoints import DEFAULT_STOCK_SELECTION_CONFIG, run_stock_selection_entry

from _entry_common import save_frame, save_text


def run_stock_selection_script() -> None:
    """运行选股脚本入口。"""
    artifact_dir = ROOT / "artifacts" / "stock_selection"
    run = run_stock_selection_entry(cache_root=artifact_dir / "cache")
    save_frame(run.signals, artifact_dir / "signals.csv")
    save_frame(run.report, artifact_dir / "report.csv")
    save_text(f"配置：{run.config_path or DEFAULT_STOCK_SELECTION_CONFIG}\n状态：完成\n", artifact_dir / "run.txt")
    print("选股入口已完成")


if __name__ == "__main__":
    run_stock_selection_script()
