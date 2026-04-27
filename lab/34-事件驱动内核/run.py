from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_UNIVERSE, Event, EventBus, ExperimentMeta, load_market_panel, record_experiment, save_csv


def main() -> None:
    meta = ExperimentMeta(
        code="34",
        title="事件驱动内核",
        goal="验证行情、信号、订单和成交可通过统一事件流串联。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    bus = EventBus()
    output: list[dict[str, object]] = []

    def handler(event: Event) -> None:
        output.append({"type": event.type, "ts": event.ts, "symbol": event.payload.get("symbol", ""), "value": event.payload.get("value", "")})
        if event.type == "market":
            bus.publish(Event("signal", event.ts, {"symbol": event.payload["symbol"], "value": event.payload["value"]}))
        elif event.type == "signal":
            bus.publish(Event("order", event.ts, {"symbol": event.payload["symbol"], "value": event.payload["value"]}))
        elif event.type == "order":
            bus.publish(Event("fill", event.ts, {"symbol": event.payload["symbol"], "value": event.payload["value"]}))

    bus.subscribe(handler)
    sample_dates = list(market.close.index[:3])
    events = [
        Event("market", sample_dates[0].strftime("%Y-%m-%d"), {"symbol": "000001", "value": float(market.close.iloc[0, 0])}),
        Event("market", sample_dates[1].strftime("%Y-%m-%d"), {"symbol": "000002", "value": float(market.close.iloc[1, 1])}),
    ]
    bus.replay(events)
    replay_a = pd.DataFrame(output)
    output.clear()
    bus.log.clear()
    bus.replay(events)
    replay_b = pd.DataFrame(output)

    artifact_dir = ROOT / "artifacts"
    save_csv(replay_a, artifact_dir / "replay_a.csv")
    save_csv(replay_b, artifact_dir / "replay_b.csv")

    deterministic = replay_a.equals(replay_b)
    chained = set(replay_a["type"]) >= {"market", "signal", "order", "fill"}
    steps = [
        "把行情事件喂入统一事件总线，由 handler 依次派生信号、订单和成交。",
        "重复回放同一事件流，检查输出是否一致。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/replay_a.csv", "artifacts/replay_b.csv"]
    if deterministic and chained:
        status = "pass"
        conclusion = "行情、信号、订单和成交已串成统一事件流。"
    else:
        status = "fail"
        conclusion = "事件驱动内核未达到预期。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
