from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_SYMBOL, ExperimentMeta, fetch_daily_history, record_experiment, save_csv


class FlakySource:
    def __init__(self, failures_before_success: int) -> None:
        self.failures_before_success = failures_before_success
        self.calls = 0

    def fetch(self):
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise TimeoutError(f"simulated timeout on attempt {self.calls}")
        return fetch_daily_history(DEFAULT_SYMBOL, "20240301", "20240315")


def main() -> None:
    meta = ExperimentMeta(
        code="02",
        title="失败恢复",
        goal="验证采集过程在超时后能否重试并在成功后继续落盘。",
        root=ROOT,
    )
    checkpoint_path = ROOT / "artifacts" / "checkpoint.txt"
    recovered_path = ROOT / "artifacts" / "recovered.csv"
    steps = [
        "构造一个前两次请求必然超时、第三次成功的源包装器。",
        "每次失败都写入当前重试次数作为断点信息。",
    ]
    artifacts = ["artifacts/checkpoint.txt", "artifacts/recovered.csv"]
    source = FlakySource(failures_before_success=2)
    status = "fail"
    conclusion = "失败恢复链路未通过。"
    try:
        for _ in range(3):
            try:
                df = source.fetch()
                save_csv(df, recovered_path)
                steps.append(f"第 {source.calls} 次请求成功并完成落盘。")
                status = "pass"
                conclusion = "重试与断点记录机制可工作，失败后可恢复到成功落盘。"
                break
            except TimeoutError as exc:
                checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
                checkpoint_path.write_text(f"attempt={source.calls}\n", encoding="utf-8")
                steps.append(f"第 {source.calls} 次请求失败并写入断点：{exc}")
        if status != "pass":
            steps.append("达到最大重试次数仍未恢复。")
    except Exception as exc:
        steps.append(f"失败恢复实验异常终止：{exc!r}")
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
