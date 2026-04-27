from __future__ import annotations

from pathlib import Path
import sys
import time

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import (
    DEFAULT_UNIVERSE,
    ExperimentMeta,
    StrategyInput,
    allocate_capital,
    build_strategy_fleet,
    load_market_panel,
    momentum_signal,
    record_experiment,
    save_csv,
)


def _build_fleet(close: pd.DataFrame, count: int) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for idx in range(count):
        data = StrategyInput(close=close, lookback=20 + (idx % 5), top_n=3)
        frame = momentum_signal(data)
        frame["strategy"] = f"s{idx:03d}"
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> None:
    meta = ExperimentMeta(
        code="43",
        title="横向扩展与负载增长",
        goal="验证策略数量增长时系统负载随之增长但接口保持一致。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    samples = [1, 10, 100]
    rows: list[dict[str, object]] = []
    for count in samples:
        start = time.perf_counter()
        fleet = _build_fleet(market.close, count)
        alloc = allocate_capital(fleet, total_cash=1_000_000.0)
        elapsed = time.perf_counter() - start
        rows.append(
            {
                "strategies": count,
                "signal_rows": len(fleet),
                "allocation_rows": len(alloc.allocation),
                "elapsed_ms": elapsed * 1000.0,
                "cash_left": alloc.cash_left,
            }
        )

    load_df = pd.DataFrame(rows)
    artifact_dir = ROOT / "artifacts"
    save_csv(load_df, artifact_dir / "load_growth.csv")

    linear_rows = list(load_df["signal_rows"])
    monotonic = linear_rows == sorted(linear_rows)
    shape_stable = (load_df["allocation_rows"] > 0).all()
    steps = [
        "把策略数量从 1 扩展到 10 再到 100，观察信号行数和分配结果。",
        "检查负载是否随策略数量单调增长，而接口形状保持一致。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/load_growth.csv"]
    if monotonic and shape_stable:
        status = "pass"
        conclusion = "横向扩展时负载可线性增长，接口没有破裂。"
    else:
        status = "fail"
        conclusion = "横向扩展未达到预期。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
