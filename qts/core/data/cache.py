from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ...paths import REPO_ROOT

_CACHE_ENV_VAR = "QTS_MARKET_CACHE_DIR"
_CACHE_SUBDIR = ".cache/qts-market"
_STATE_FILENAME = "state.json"
CACHE_COLUMNS = ["date", "symbol", "close", "volume", "amount", "provider"]


def default_cache_root() -> Path:
    """返回默认缓存根目录。"""
    override = os.getenv(_CACHE_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return REPO_ROOT / _CACHE_SUBDIR


def state_path(cache_root: Path) -> Path:
    """返回状态文件路径。"""
    return cache_root / _STATE_FILENAME


def symbol_cache_path(cache_root: Path, symbol: str) -> Path:
    """返回单标的缓存路径。"""
    return cache_root / "symbols" / f"{symbol}.parquet"


def parse_date(value: str | pd.Timestamp) -> pd.Timestamp:
    """把日期值转为归一化时间戳。"""
    return pd.to_datetime(value).normalize()


def format_date(value: pd.Timestamp | None) -> str | None:
    """把日期格式化为标准字符串。"""
    if value is None:
        return None
    return pd.Timestamp(value).normalize().strftime("%Y-%m-%d")


def compact_date(value: pd.Timestamp) -> str:
    """把日期格式化为紧凑字符串。"""
    return pd.Timestamp(value).normalize().strftime("%Y%m%d")


def ensure_history_frame(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """把历史数据整理成缓存帧。"""
    frame = df.copy()
    if "date" not in frame.columns:
        if isinstance(frame.index, pd.DatetimeIndex) or frame.index.name == "date":
            frame = frame.reset_index()
        elif "时间" in frame.columns:
            frame = frame.rename(columns={"时间": "date"})
        elif "日期" in frame.columns:
            frame = frame.rename(columns={"日期": "date"})
    if "date" not in frame.columns:
        raise ValueError("历史数据缺少 date 日期列")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["symbol"] = symbol
    for column in ["close", "volume", "amount"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        else:
            frame[column] = pd.NA
    if "provider" in frame.columns:
        frame["provider"] = frame["provider"].fillna("unknown").astype(str)
    else:
        frame["provider"] = str(df.attrs.get("provider", "unknown"))
    frame = frame[CACHE_COLUMNS].dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return frame


def read_cache_frame(path: Path) -> pd.DataFrame:
    """读取缓存数据帧。"""
    if not path.exists():
        return pd.DataFrame(columns=CACHE_COLUMNS)
    try:
        return pd.read_parquet(path)
    except ImportError as exc:
        raise RuntimeError("Parquet 缓存依赖 pyarrow 或 fastparquet") from exc


def write_cache_frame(df: pd.DataFrame, path: Path) -> None:
    """写入缓存数据帧。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    try:
        df.to_parquet(tmp_path, index=False)
    except ImportError as exc:
        raise RuntimeError("Parquet 缓存依赖 pyarrow 或 fastparquet") from exc
    tmp_path.replace(path)


def load_state(path: Path) -> dict[str, object]:
    """读取缓存状态。"""
    if not path.exists():
        return {"version": 1, "updated_at": None, "symbols": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "updated_at": None, "symbols": {}}
    if not isinstance(payload, dict):
        return {"version": 1, "updated_at": None, "symbols": {}}
    payload.setdefault("version", 1)
    payload.setdefault("updated_at", None)
    payload.setdefault("symbols", {})
    return payload


def write_state(path: Path, payload: dict[str, object]) -> None:
    """写入缓存状态。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def missing_ranges(
    requested_start: pd.Timestamp,
    requested_end: pd.Timestamp,
    cached_start: pd.Timestamp | None,
    cached_end: pd.Timestamp | None,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """计算还需要补拉的日期区间。"""
    if cached_start is None or cached_end is None:
        return [(requested_start, requested_end)]

    ranges: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    if requested_start < cached_start:
        prefix_end = min(requested_end, cached_start - pd.Timedelta(days=1))
        if prefix_end >= requested_start:
            ranges.append((requested_start, prefix_end))
    if requested_end > cached_end:
        suffix_start = cached_end + pd.Timedelta(days=1)
        if suffix_start <= requested_end:
            ranges.append((suffix_start, requested_end))
    return ranges


def merge_history_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """合并多段缓存历史。"""
    if not frames:
        return pd.DataFrame(columns=CACHE_COLUMNS)
    merged = pd.concat(frames, ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"]).dt.normalize()
    merged["close"] = pd.to_numeric(merged["close"], errors="coerce")
    merged["volume"] = pd.to_numeric(merged["volume"], errors="coerce")
    merged["amount"] = pd.to_numeric(merged["amount"], errors="coerce")
    merged["provider"] = merged["provider"].fillna("unknown").astype(str) if "provider" in merged.columns else "unknown"
    merged = (
        merged.sort_values("date", kind="mergesort")
        .drop_duplicates(subset=["date"], keep="last")
        .reset_index(drop=True)
    )
    return merged[CACHE_COLUMNS]


def updated_at() -> str:
    """返回当前 UTC 时间戳字符串。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
