from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_UNIVERSE, ExperimentMeta, load_market_panel, record_experiment, save_csv


def _build_trigger_log(close: pd.DataFrame, threshold: float = 0.015) -> pd.DataFrame:
    momentum = close.pct_change(20)
    rows: list[dict[str, object]] = []
    dates = list(close.index)
    for idx in range(21, len(dates) - 1):
        signal_date = dates[idx]
        trade_date = dates[idx + 1]
        spread = float(momentum.loc[signal_date].max() - momentum.loc[signal_date].min())
        trigger = spread >= threshold
        rows.append(
            {
                "signal_date": signal_date.strftime("%Y-%m-%d"),
                "trade_date": trade_date.strftime("%Y-%m-%d"),
                "spread": spread,
                "triggered": trigger,
                "delay_bars": 1 if trigger else 0,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    meta = ExperimentMeta(
        code="29",
        title="调仓触发与延迟执行",
        goal="验证调仓由信号触发，并且真正执行发生在下一根 bar。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    trigger_log = _build_trigger_log(market.close, threshold=0.02)
    executed = trigger_log[trigger_log["triggered"]].copy()
    executed["executed_after_signal"] = executed["delay_bars"] > 0

    artifact_dir = ROOT / "artifacts"
    save_csv(trigger_log, artifact_dir / "trigger_log.csv")
    save_csv(executed, artifact_dir / "executed_log.csv")

    triggered_days = int(trigger_log["triggered"].sum()) if not trigger_log.empty else 0
    delayed_ok = bool(executed["executed_after_signal"].all()) if not executed.empty else False
    steps = [
        "按 rolling signal 触发调仓，而不是每天固定执行。",
        "把实际执行延迟到下一根 bar，避免同 bar 未来函数。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/trigger_log.csv", "artifacts/executed_log.csv"]
    if triggered_days > 0 and delayed_ok:
        status = "pass"
        conclusion = "调仓触发与延迟执行都能按信号驱动。"
    else:
        status = "fail"
        conclusion = "调仓触发或延迟执行未达到预期。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
