from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import (
    AccountState,
    Event,
    EventBus,
    ExperimentMeta,
    record_experiment,
    reserve_cash,
    save_csv,
)


def main() -> None:
    meta = ExperimentMeta(
        code="37",
        title="分层风控拦截",
        goal="验证组合级、账户级和订单级风控可以分别拦截。",
        root=ROOT,
    )
    account = AccountState(cash=100_000.0)
    bus = EventBus()
    log: list[dict[str, object]] = []

    def handler(event: Event) -> None:
        if event.type == "signal" and float(event.payload.get("score", 0.0)) < 0:
            log.append({"layer": "strategy", "blocked": True, "reason": "negative score"})
            return
        if event.type == "order" and float(event.payload.get("notional", 0.0)) > account.cash:
            log.append({"layer": "account", "blocked": True, "reason": "insufficient cash"})
            return
        if event.type == "fill" and float(event.payload.get("size", 0.0)) > 5000:
            log.append({"layer": "execution", "blocked": True, "reason": "order too large"})
            return
        log.append({"layer": "pass", "blocked": False, "reason": ""})

    bus.subscribe(handler)
    bus.replay(
        [
            Event("signal", "2024-01-02", {"score": -1.0}),
            Event("order", "2024-01-02", {"notional": 200_000.0}),
            Event("fill", "2024-01-02", {"size": 10_000.0}),
        ]
    )
    reserved = reserve_cash(account, "ord-x", 20_000.0)

    artifact_dir = ROOT / "artifacts"
    save_csv(pd.DataFrame(log), artifact_dir / "risk_blocks.csv")
    save_csv(pd.DataFrame([account.snapshot(), reserved.snapshot()]), artifact_dir / "account_snapshot.csv")

    blocked_layers = {row["layer"] for row in log if row["blocked"]}
    steps = [
        "分别喂入负信号、超现金订单和超大成交，触发三层不同风控。",
        "确认拦截点能落在策略、账户和执行三个层次。",
    ]
    artifacts = ["artifacts/risk_blocks.csv", "artifacts/account_snapshot.csv"]
    if {"strategy", "account", "execution"}.issubset(blocked_layers):
        status = "pass"
        conclusion = "风控已分层，不再只依赖策略内部阈值。"
    else:
        status = "fail"
        conclusion = "分层风控拦截未达到预期。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
