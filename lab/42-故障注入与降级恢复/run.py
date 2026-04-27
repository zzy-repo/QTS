from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import AccountState, DEFAULT_UNIVERSE, ExperimentMeta, load_market_panel, record_experiment, reserve_cash, save_csv


def main() -> None:
    meta = ExperimentMeta(
        code="42",
        title="故障注入与降级恢复",
        goal="验证模块故障后系统能降级运行并恢复状态。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    account = AccountState(cash=1_000_000.0)
    snapshot = account.snapshot()
    logs: list[dict[str, object]] = []
    recovered = False

    try:
        account = reserve_cash(account, "ord-1", 250_000.0)
        logs.append({"stage": "reserve", "status": "ok"})
        raise RuntimeError("simulated matching crash")
    except Exception as exc:
        logs.append({"stage": "match", "status": "fail", "error": str(exc)})
        account = AccountState.restore(snapshot)
        recovered = True
        logs.append({"stage": "restore", "status": "ok"})

    degradation = pd.DataFrame(logs)
    artifact_dir = ROOT / "artifacts"
    save_csv(degradation, artifact_dir / "fault_log.csv")
    save_csv(pd.DataFrame([snapshot, account.snapshot()]), artifact_dir / "snapshots.csv")

    state_clean = account.snapshot() == snapshot
    steps = [
        "主动注入撮合阶段异常，观察系统是否进入降级路径。",
        "从快照恢复账户状态，检查状态是否被污染。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/fault_log.csv", "artifacts/snapshots.csv"]
    if recovered and state_clean:
        status = "pass"
        conclusion = "故障可降级恢复，状态未污染。"
    else:
        status = "fail"
        conclusion = "故障注入后恢复失败。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
