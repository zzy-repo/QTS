from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import AccountState, ExperimentMeta, apply_fill, record_experiment, reserve_cash, save_csv


def main() -> None:
    meta = ExperimentMeta(
        code="32",
        title="账户模型与冻结资金",
        goal="验证现金、冻结资金和持仓状态可隔离更新。",
        root=ROOT,
    )
    account = AccountState(cash=1_000_000.0)
    reserved = reserve_cash(account, "ord-001", 200_000.0)
    filled = apply_fill(reserved, "000001", 1_000.0, 10.0, "ord-001")
    snapshot = filled.snapshot()
    restored = AccountState.restore(snapshot)

    prices = pd.Series({"000001": 10.5})
    base_equity = account.equity(prices)
    final_equity = restored.equity(prices)

    artifact_dir = ROOT / "artifacts"
    save_csv(pd.DataFrame([account.snapshot(), reserved.snapshot(), filled.snapshot()]), artifact_dir / "account_flow.csv")

    isolated = account.cash == 1_000_000.0 and reserved.frozen_cash == 200_000.0 and "ord-001" not in restored.in_flight_orders
    equity_ok = final_equity != base_equity
    steps = [
        "创建初始账户，先冻结现金，再撮合成交，最后做快照和恢复。",
        "检查冻结资金、持仓和未完成订单是否互不污染。",
    ]
    artifacts = ["artifacts/account_flow.csv"]
    if isolated and equity_ok:
        status = "pass"
        conclusion = "账户现金、冻结资金和持仓状态可独立维护。"
    else:
        status = "fail"
        conclusion = "账户模型隔离性不足。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
