from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import ExperimentMeta, build_ohlcv_frame, load_market_panel, quality_checks, record_experiment, save_csv


def main() -> None:
    meta = ExperimentMeta(
        code="18",
        title="数据一致性与污染",
        goal="验证缺失、重复和异常值可被识别，并且填充后可恢复。",
        root=ROOT,
    )
    market = load_market_panel(["000001"], "20240102", "20240315")
    clean = build_ohlcv_frame(market)
    polluted = clean.copy()
    polluted = pd.concat([polluted.iloc[:8], polluted.iloc[[3]], polluted.iloc[8:]], ignore_index=True)
    polluted.loc[2, "close"] = -1.0
    polluted.loc[5, "high"] = polluted.loc[5, "low"] - 0.5
    polluted.loc[6, "volume"] = -100.0

    missing = clean.copy()
    missing.loc[7, "close"] = pd.NA
    missing.loc[7, "open"] = pd.NA
    missing["close"] = missing["close"].ffill()
    missing["open"] = missing["open"].ffill()

    clean_issues = quality_checks(clean)
    polluted_issues = quality_checks(polluted)
    filled_issues = quality_checks(missing)

    artifact_dir = ROOT / "artifacts"
    save_csv(clean.head(50), artifact_dir / "clean.csv")
    save_csv(polluted.head(50), artifact_dir / "polluted.csv")
    save_csv(missing.head(50), artifact_dir / "filled.csv")

    steps = [
        "基于同一面板生成标准 OHLCV 结构。",
        "注入重复日期、负价格、异常高低点和负成交量。",
        "对缺失值执行前向填充后再次校验。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = [
        "artifacts/clean.csv",
        "artifacts/polluted.csv",
        "artifacts/filled.csv",
    ]
    if not clean_issues and polluted_issues and not filled_issues:
        status = "pass"
        conclusion = "数据污染可识别，缺失填充后可恢复到可用状态。"
    else:
        status = "fail"
        conclusion = "一致性或污染检测未达到预期。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
