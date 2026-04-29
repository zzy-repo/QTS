from __future__ import annotations

from _bootstrap import ROOT
from loguru import logger
from qts.core.data.data_source import describe_source_mode
from qts.infra.entrypoints import DEFAULT_BACKTEST_CONFIG, run_backtest_entry
from qts.infra.logging_utils import configure_logging

from _entry_common import save_frame, save_text


def run_backtest_script() -> None:
    """运行回测脚本入口。"""
    artifact_dir = ROOT / "artifacts" / "backtest"
    log_path = configure_logging("backtest", artifact_dir)
    logger.info("回测脚本启动 输出目录={} 日志路径={}", artifact_dir, log_path)
    run = run_backtest_entry()
    save_frame(run.signals, artifact_dir / "signals.csv")
    save_frame(run.result.aggregate_pnl, artifact_dir / "pnl.csv")
    save_frame(run.report, artifact_dir / "report.csv")
    save_text(
        f"配置：{run.config_path or DEFAULT_BACKTEST_CONFIG}\n状态：完成\n数据来源：{describe_source_mode(run.market.source_mode)} ({run.market.source_mode})\n",
        artifact_dir / "run.txt",
    )
    logger.info(
        "回测脚本完成 配置路径={} 数据来源={}({})",
        run.config_path or DEFAULT_BACKTEST_CONFIG,
        describe_source_mode(run.market.source_mode),
        run.market.source_mode,
    )
    print("回测入口已完成")


if __name__ == "__main__":
    run_backtest_script()
