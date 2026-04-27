from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import AccountState, ExperimentMeta, record_experiment, save_csv


def main() -> None:
    meta = ExperimentMeta(
        code="35",
        title="状态快照与恢复",
        goal="验证任意时点状态快照可恢复。",
        root=ROOT,
    )
    account = AccountState(cash=500_000.0, positions={"000001": 1000.0, "600519": 20.0}, in_flight_orders={"ord-1": {"status": "NEW"}})
    snapshot = account.snapshot()
    restored = AccountState.restore(snapshot)
    prices = pd.Series({"000001": 10.0, "600519": 1500.0})

    artifact_dir = ROOT / "artifacts"
    save_csv(pd.DataFrame([snapshot, restored.snapshot()]), artifact_dir / "snapshots.csv")

    same_payload = snapshot == restored.snapshot()
    same_equity = abs(account.equity(prices) - restored.equity(prices)) < 1e-9
    steps = [
        "把账户、持仓和在途订单打成快照。",
        "从快照恢复后重新计算权益，检查恢复结果是否一致。",
    ]
    artifacts = ["artifacts/snapshots.csv"]
    if same_payload and same_equity:
        status = "pass"
        conclusion = "任意时点状态可快照并恢复，权益一致。"
    else:
        status = "fail"
        conclusion = "状态快照与恢复未达到预期。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
