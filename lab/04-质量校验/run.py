from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import (
    DEFAULT_SYMBOL,
    ExperimentMeta,
    fetch_daily_history,
    normalize_daily_history,
    quality_checks,
    record_experiment,
    save_csv,
)


def main() -> None:
    meta = ExperimentMeta(
        code="04",
        title="质量校验",
        goal="验证标准化数据能否通过最小质量检查规则。",
        root=ROOT,
    )
    checked_path = ROOT / "artifacts" / "checked.csv"
    steps = [
        "抓取并标准化一段最小日线数据。",
        "执行空值、重复、排序、价格区间、成交量等最小规则检查。",
    ]
    artifacts = ["artifacts/checked.csv"]
    try:
        raw_df = fetch_daily_history(DEFAULT_SYMBOL, "20240301", "20240315")
        normalized_df = normalize_daily_history(raw_df, DEFAULT_SYMBOL)
        save_csv(normalized_df, checked_path)
        issues = quality_checks(normalized_df)
        if issues:
            steps.extend(f"发现问题：{issue}" for issue in issues)
            status = "fail"
            conclusion = "质量校验已能发现异常，但当前样本未完全通过最小规则。"
        else:
            steps.append("未发现空值、重复、排序和基础价格区间异常。")
            status = "pass"
            conclusion = "最小质量校验规则可执行，当前样本通过基础可用性检查。"
    except Exception as exc:
        steps.append(f"质量校验实验失败：{exc!r}")
        status = "fail"
        conclusion = "质量校验链路未通过，需先解决标准化或规则执行问题。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
