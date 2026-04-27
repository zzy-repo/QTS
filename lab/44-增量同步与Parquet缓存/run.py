from __future__ import annotations

from pathlib import Path
import sys
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))
sys.path.insert(0, str(LAB_ROOT.parent))

from qts import data_source as ds
from shared import ExperimentMeta, record_experiment


def _make_history(start_date: str, end_date: str, *, overlap_revision: bool = False) -> pd.DataFrame:
    dates = pd.bdate_range(pd.to_datetime(start_date), pd.to_datetime(end_date))
    idx = np.arange(len(dates), dtype=float)
    close = 100.0 + idx
    if overlap_revision and pd.Timestamp(start_date) == pd.Timestamp("2024-01-31"):
        close = close.copy()
        close[0] = 9999.0
    return pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "symbol": "000001",
            "close": close,
            "volume": 1_000_000.0 + idx * 1_000.0,
            "amount": (100.0 + idx) * (1_000_000.0 + idx * 1_000.0),
        }
    )


def main() -> None:
    meta = ExperimentMeta(
        code="44",
        title="增量同步与Parquet缓存",
        goal="验证本地 Parquet 缓存、尾部补拉、去重合并和断点状态写回。",
        root=ROOT,
    )

    artifact_dir = ROOT / "artifacts"
    cache_root = artifact_dir / "cache"
    state_path = cache_root / "state.json"
    cache_store: dict[Path, pd.DataFrame] = {}
    fetch_calls: list[tuple[str, str, str]] = []

    def fake_read_cache(path: Path) -> pd.DataFrame:
        frame = cache_store.get(path)
        if frame is None:
            return pd.DataFrame(columns=["date", "symbol", "close", "volume", "amount"])
        return frame.copy()

    def fake_write_cache(frame: pd.DataFrame, path: Path) -> None:
        cache_store[path] = frame.copy()

    def fake_fetcher(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        fetch_calls.append((symbol, start_date, end_date))
        return _make_history(start_date, end_date, overlap_revision=True)

    original_sync = ds.sync_symbol_history

    def sync_for_lab(symbol: str, start_date: str, end_date: str, *, cache_root: Path | None = None, **_: object):
        return original_sync(
            symbol,
            start_date,
            end_date,
            cache_root=cache_root,
            fetcher=fake_fetcher,
            read_cache=fake_read_cache,
            write_cache=fake_write_cache,
        )

    try:
        ds.sync_symbol_history = sync_for_lab  # type: ignore[assignment]
        first = ds.sync_symbol_history(
            "000001",
            "20240102",
            "20240131",
            cache_root=cache_root,
            fetcher=fake_fetcher,
            read_cache=fake_read_cache,
            write_cache=fake_write_cache,
        )
        second = ds.sync_symbol_history(
            "000001",
            "20240201",
            "20240229",
            cache_root=cache_root,
            fetcher=fake_fetcher,
            read_cache=fake_read_cache,
            write_cache=fake_write_cache,
        )
        third = ds.sync_symbol_history(
            "000001",
            "20240201",
            "20240229",
            cache_root=cache_root,
            fetcher=fake_fetcher,
            read_cache=fake_read_cache,
            write_cache=fake_write_cache,
        )
        market = ds.load_market_panel(["000001"], "20240102", "20240229", cache_root=cache_root)
    finally:
        ds.sync_symbol_history = original_sync  # type: ignore[assignment]

    state = json.loads(state_path.read_text(encoding="utf-8"))
    cached_frame = cache_store[first.cache_path].copy()
    jan_31_close = float(cached_frame.loc[pd.to_datetime(cached_frame["date"]) == pd.Timestamp("2024-01-31"), "close"].iloc[0])

    overlap_ok = jan_31_close == 9999.0
    first_fetch_ok = first.network_hit and first.fetched_ranges == [("2024-01-02", "2024-01-31")]
    second_fetch_ok = second.network_hit and second.fetched_ranges == [("2024-01-31", "2024-02-29")]
    third_cache_only = (not third.network_hit) and third.fetched_ranges == []
    panel_ok = market.source_mode == "cache" and len(market.close) == len(second.cache_frame)
    state_ok = state["symbols"]["000001"]["stored_end"] == "2024-02-29"
    fetch_ok = fetch_calls == [
        ("000001", "20240102", "20240131"),
        ("000001", "20240131", "20240229"),
    ]

    steps = [
        "首次同步写入 Jan 窗口缓存。",
        "二次同步只补拉从最新缓存日开始的尾部，并用重叠日覆盖旧值。",
        "三次同步完全命中缓存，再次加载时无需网络请求。",
    ]
    artifacts = [
        "artifacts/cache/state.json",
    ]

    if overlap_ok and first_fetch_ok and second_fetch_ok and third_cache_only and panel_ok and state_ok and fetch_ok:
        status = "pass"
        conclusion = "增量同步、Parquet 缓存和断点状态链路可工作。"
    else:
        status = "fail"
        conclusion = "增量同步链路存在偏差。"

    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
