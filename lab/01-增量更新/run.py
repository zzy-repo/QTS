from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_SYMBOL, ExperimentMeta, fetch_daily_history, record_experiment, save_csv


def main() -> None:
    meta = ExperimentMeta(
        code="01",
        title="增量更新",
        goal="验证首次拉取与后续按时间窗口增量补齐能否形成连续结果。",
        root=ROOT,
    )
    first_path = ROOT / "artifacts" / "first.csv"
    second_path = ROOT / "artifacts" / "second.csv"
    merged_path = ROOT / "artifacts" / "merged.csv"
    steps = [
        "将 2024-01-02 至 2024-01-31 作为首次窗口。",
        "将 2024-02-01 至 2024-02-29 作为增量窗口。",
    ]
    artifacts = ["artifacts/first.csv", "artifacts/second.csv", "artifacts/merged.csv"]
    try:
        first_df = fetch_daily_history(DEFAULT_SYMBOL, "20240102", "20240131")
        second_df = fetch_daily_history(DEFAULT_SYMBOL, "20240201", "20240229")
        save_csv(first_df, first_path)
        save_csv(second_df, second_path)
        merged = (
            pd.concat([first_df, second_df], ignore_index=True)
            .drop_duplicates(subset=["date"], keep="last")
            .sort_values("date")
            .reset_index(drop=True)
        )
        save_csv(merged, merged_path)
        steps.append(f"首次窗口 {len(first_df)} 行，增量窗口 {len(second_df)} 行。")
        steps.append(f"合并后 {len(merged)} 行，按日期去重并排序。")
        status = "pass"
        conclusion = "全量首拉与时间窗口增量补齐可形成连续数据集。"
    except Exception as exc:
        steps.append(f"增量实验失败：{exc!r}")
        status = "fail"
        conclusion = "增量补齐链路未通过，需先解决时间窗口请求或合并逻辑。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
