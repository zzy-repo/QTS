from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_UNIVERSE, ExperimentMeta, load_market_panel, record_experiment, save_csv, simulate_match


def main() -> None:
    meta = ExperimentMeta(
        code="33",
        title="订单生命周期与异步撮合",
        goal="验证订单可以按 NEW / PARTIAL / FILLED / CANCEL 流转。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    price = float(market.close.iloc[0, 0])
    full = simulate_match("ord-full", "000001", 1000.0, price, available_volume=5000.0, ts="2024-01-02")
    partial = simulate_match("ord-partial", "000001", 3000.0, price, available_volume=1000.0, ts="2024-01-02")
    canceled = simulate_match("ord-cancel", "000001", 1000.0, price, available_volume=0.0, ts="2024-01-02")

    rows = [
        {"order_id": ev.order_id, "symbol": ev.symbol, "shares": ev.shares, "price": ev.price, "status": ev.status, "ts": ev.ts}
        for ev in full + partial + canceled
    ]
    frame = pd.DataFrame(rows)
    artifact_dir = ROOT / "artifacts"
    save_csv(frame, artifact_dir / "order_lifecycle.csv")

    lifecycle_ok = {"NEW", "PARTIAL", "FILLED", "CANCEL"}.issuperset(set(frame["status"]))
    async_ok = frame.groupby("order_id")["status"].first().eq("NEW").all()
    steps = [
        "对满额、部分成交和取消三种订单分别生成生命周期事件。",
        "把订单状态落成事件表，验证状态机可追踪。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/order_lifecycle.csv"]
    if lifecycle_ok and async_ok:
        status = "pass"
        conclusion = "订单生命周期可追踪，撮合结果可被状态机表达。"
    else:
        status = "fail"
        conclusion = "订单生命周期或异步撮合未达到预期。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
