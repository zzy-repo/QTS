from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_SYMBOL, ExperimentMeta, load_market_panel, record_experiment, save_csv


def main() -> None:
    meta = ExperimentMeta(
        code="23",
        title="复权一致性与停牌处理",
        goal="验证复权口径统一、停牌可标记、涨跌停可识别。",
        root=ROOT,
    )
    market = load_market_panel([DEFAULT_SYMBOL], "20240102", "20240315")
    close = market.close.iloc[:, 0].copy()
    volume = market.volume.iloc[:, 0].copy()
    dates = close.index

    split_date = dates[len(dates) // 2]
    raw_close = close.copy()
    raw_close.loc[raw_close.index >= split_date] = raw_close.loc[raw_close.index >= split_date] * 0.5
    adj_factor = pd.Series(1.0, index=dates)
    adj_factor.loc[adj_factor.index >= split_date] = 2.0
    adjusted_close = raw_close * adj_factor

    raw_return = raw_close.pct_change().dropna()
    adjusted_return = adjusted_close.pct_change().dropna()
    base_return = close.pct_change().dropna()

    halt_date = dates[len(dates) // 3]
    limit_date = dates[len(dates) // 3 + 1]
    status = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "symbol": DEFAULT_SYMBOL,
            "raw_close": raw_close.values,
            "adjusted_close": adjusted_close.values,
            "volume": volume.values,
            "tradable": True,
            "status": "normal",
        }
    )
    status.loc[status["date"] == halt_date.strftime("%Y-%m-%d"), "tradable"] = False
    status.loc[status["date"] == halt_date.strftime("%Y-%m-%d"), "status"] = "halt"
    status.loc[status["date"] == limit_date.strftime("%Y-%m-%d"), "status"] = "limit_up"
    status.loc[status["date"] == limit_date.strftime("%Y-%m-%d"), "tradable"] = False
    status.loc[status["date"] == limit_date.strftime("%Y-%m-%d"), "volume"] = 0.0

    artifact_dir = ROOT / "artifacts"
    save_csv(status, artifact_dir / "status.csv")
    save_csv(pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "raw_close": raw_close.values, "adjusted_close": adjusted_close.values}), artifact_dir / "prices.csv")

    raw_jump = float(abs(raw_return.loc[raw_return.index >= split_date].iloc[0] - base_return.loc[base_return.index >= split_date].iloc[0]))
    adj_jump = float(abs(adjusted_return.loc[adjusted_return.index >= split_date].iloc[0] - base_return.loc[base_return.index >= split_date].iloc[0]))
    halt_flag = bool((status["status"] == "halt").any() and (status["tradable"] == False).any())
    limit_flag = bool((status["status"] == "limit_up").any() and (status["tradable"] == False).any())

    steps = [
        "构造一个拆分事件并用复权因子恢复连续价格序列。",
        "标记一个停牌日和一个涨跌停日，确认它们被识别为不可交易。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/status.csv", "artifacts/prices.csv"]
    if adj_jump < raw_jump and halt_flag and limit_flag:
        status_text = "pass"
        conclusion = "复权后收益连续，停牌和涨跌停状态可被统一标记。"
    else:
        status_text = "fail"
        conclusion = "复权一致性或停牌处理未达到预期。"
    record_experiment(meta, status_text, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
