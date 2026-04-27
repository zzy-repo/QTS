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
    record_experiment,
    save_csv,
)


def main() -> None:
    meta = ExperimentMeta(
        code="03",
        title="标准化",
        goal="验证原始行情字段能否转换为统一标准结构。",
        root=ROOT,
    )
    raw_path = ROOT / "artifacts" / "source.csv"
    normalized_path = ROOT / "artifacts" / "normalized.csv"
    steps = [
        "抓取一段最小原始日线数据。",
        "将中文字段映射为统一英文标准字段，并补齐 symbol 列。",
    ]
    artifacts = ["artifacts/source.csv", "artifacts/normalized.csv"]
    try:
        raw_df = fetch_daily_history(DEFAULT_SYMBOL, "20240301", "20240315")
        normalized_df = normalize_daily_history(raw_df, DEFAULT_SYMBOL)
        save_csv(raw_df, raw_path)
        save_csv(normalized_df, normalized_path)
        steps.append(f"标准化后字段数 {len(normalized_df.columns)}，样本数 {len(normalized_df)}。")
        status = "pass"
        conclusion = "原始返回可稳定映射到统一字段结构，适合作为下游输入。"
    except Exception as exc:
        steps.append(f"标准化实验失败：{exc!r}")
        status = "fail"
        conclusion = "标准化链路未通过，需先处理源字段或类型转换问题。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
