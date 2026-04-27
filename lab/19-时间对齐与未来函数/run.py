from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import ExperimentMeta, audit_alignment, load_market_panel, record_experiment, save_csv


def _build_alignment(close: pd.DataFrame, lookback: int = 20, top_n: int = 3) -> pd.DataFrame:
    momentum = close.pct_change(lookback)
    dates = list(close.index)
    rows: list[dict[str, object]] = []
    for idx in range(lookback, len(dates) - 2):
        signal_date = dates[idx]
        trade_date = dates[idx + 1]
        pnl_date = dates[idx + 2]
        selected = momentum.loc[signal_date].dropna().sort_values(ascending=False).head(top_n)
        for rank, (symbol, score) in enumerate(selected.items(), start=1):
            rows.append(
                {
                    "signal_date": signal_date.strftime("%Y-%m-%d"),
                    "trade_date": trade_date.strftime("%Y-%m-%d"),
                    "pnl_date": pnl_date.strftime("%Y-%m-%d"),
                    "symbol": symbol,
                    "rank": rank,
                    "score": float(score),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    meta = ExperimentMeta(
        code="19",
        title="时间对齐与未来函数",
        goal="验证信号、成交价、持仓和收益严格按时间顺序对齐。",
        root=ROOT,
    )
    market = load_market_panel(["000001", "000002", "600519"], "20240102", "20240315")
    alignment = _build_alignment(market.close)
    bad_alignment = alignment.copy()
    if not bad_alignment.empty:
        bad_alignment["trade_date"] = bad_alignment["signal_date"]

    clean_issues = audit_alignment(alignment)
    bad_issues = audit_alignment(bad_alignment)

    artifact_dir = ROOT / "artifacts"
    save_csv(alignment.head(100), artifact_dir / "alignment.csv")
    save_csv(bad_alignment.head(100), artifact_dir / "bad_alignment.csv")

    steps = [
        "用过去 20 日收益生成信号，并把成交和收益顺延到后续交易日。",
        "构造一个未来函数负样本，把 trade_date 人为回写到 signal_date。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/alignment.csv", "artifacts/bad_alignment.csv"]
    if not clean_issues and bad_issues:
        status = "pass"
        conclusion = "时间链路满足严格顺序，未来函数样本可被审计发现。"
    else:
        status = "fail"
        conclusion = "时间对齐审计未达到预期。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
