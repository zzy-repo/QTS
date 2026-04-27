from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_SYMBOL, ExperimentMeta, fetch_daily_history, record_experiment, save_csv


def main() -> None:
    meta = ExperimentMeta(
        code="00",
        title="数据源连通性",
        goal="验证单一数据源能否成功请求、解析并落盘最小历史行情数据。",
        root=ROOT,
    )
    raw_path = ROOT / "artifacts" / "source.csv"
    steps = [
        "选择东财历史行情直连接口作为单一数据源。",
        f"请求标的 {DEFAULT_SYMBOL} 在 2024-03-01 至 2024-03-15 的日线数据。",
    ]
    artifacts = [f"artifacts/source.csv"]
    try:
        df = fetch_daily_history(DEFAULT_SYMBOL, "20240301", "20240315")
        steps.append(f"收到 {len(df)} 行原始数据。")
        save_csv(df, raw_path)
        steps.append("原始数据已落盘。")
        status = "pass"
        conclusion = "单源连通、返回结构可解析、原始数据可稳定落盘。"
    except Exception as exc:
        steps.append(f"请求或落盘失败：{exc!r}")
        status = "fail"
        conclusion = "单源连通性未通过，需先解决源可达性或返回格式问题。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
