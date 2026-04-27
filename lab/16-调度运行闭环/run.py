from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import (
    DEFAULT_UNIVERSE,
    ExperimentMeta,
    build_momentum_portfolio,
    load_market_panel,
    record_experiment,
    save_csv,
)


def main() -> None:
    meta = ExperimentMeta(
        code="16",
        title="调度运行闭环",
        goal="验证系统可按周期自动运行。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    dates = list(market.close.index)
    logs: list[dict[str, object]] = []

    warmup = 20
    for i in range(warmup + 1, min(len(dates), warmup + 6)):
        current = market.close.iloc[: i + 1]
        current_market = type(market)(close=current, volume=market.volume.iloc[: i + 1], amount=market.amount.iloc[: i + 1], source_mode=market.source_mode)
        run = build_momentum_portfolio(current_market.close, lookback=20, top_n=3, scheme="equal")
        logs.append(
            {
                "run_date": dates[i].strftime("%Y-%m-%d"),
                "status": "pass" if not run.pnl.empty else "fail",
                "orders": len(run.holdings),
                "pnl_rows": len(run.pnl),
                "source_mode": market.source_mode,
            }
        )

    log_df = pd.DataFrame(logs)
    log_path = ROOT / "artifacts" / "schedule_log.csv"
    save_csv(log_df, log_path)

    steps = [
        "以每日收盘后自动执行的方式模拟多日连续运行。",
        f"面板来源：{market.source_mode}。",
        f"写入 {len(log_df)} 条调度日志。",
    ]
    artifacts = ["artifacts/schedule_log.csv"]
    if not log_df.empty and (log_df["status"] == "pass").all():
        status = "pass"
        conclusion = "系统可按周期自动运行，多日连续执行无人工干预。"
    else:
        status = "fail"
        conclusion = "调度运行未能稳定执行。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
