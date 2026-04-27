from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Callable

import httpx
import numpy as np
import pandas as pd

from .models import MarketPanel

DEFAULT_SYMBOL = "000001"
DEFAULT_UNIVERSE = ["000001", "000002", "600519", "601318", "300750"]

RAW_COLUMN_MAP = {
    "日期": "date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "涨跌幅": "pct_change",
    "涨跌额": "change",
    "换手率": "turnover",
}

STANDARD_COLUMNS = [
    "symbol",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "amplitude",
    "pct_change",
    "change",
    "turnover",
]

_CACHE_ENV_VAR = "QTS_MARKET_CACHE_DIR"
_CACHE_SUBDIR = ".cache/qts-market"
_STATE_FILENAME = "state.json"
_CACHE_COLUMNS = ["date", "symbol", "close", "volume", "amount"]


@dataclass(frozen=True)
class SyncResult:
    """描述单个标的同步结果。"""

    frame: pd.DataFrame
    cache_frame: pd.DataFrame
    cache_path: Path
    state_path: Path
    cache_hit: bool
    network_hit: bool
    fetched_ranges: list[tuple[str, str]]
    source_mode: str


def fetch_daily_history(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """获取单标的历史日线。"""
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": "101",
        "fqt": "1",
        "secid": f"0.{symbol}",
        "beg": start_date,
        "end": end_date,
    }
    with httpx.Client(timeout=15, follow_redirects=True, trust_env=False) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    klines = payload["data"]["klines"]
    df = pd.DataFrame([row.split(",") for row in klines])
    df.columns = [
        "date",
        "open",
        "close",
        "high",
        "low",
        "volume",
        "amount",
        "amplitude",
        "pct_change",
        "change",
        "turnover",
    ]
    df["symbol"] = symbol
    df = df[STANDARD_COLUMNS]
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df


def normalize_daily_history(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """标准化原始日线字段。"""
    normalized = df.rename(columns=RAW_COLUMN_MAP).copy()
    if "date" not in normalized.columns and "时间" in normalized.columns:
        normalized = normalized.rename(columns={"时间": "date"})
    normalized["symbol"] = symbol
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.strftime("%Y-%m-%d")
    for column in STANDARD_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = pd.NA
    return normalized[STANDARD_COLUMNS].sort_values("date").reset_index(drop=True)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    """保存 CSV 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def quality_checks(df: pd.DataFrame) -> list[str]:
    """执行基础质量检查。"""
    issues: list[str] = []
    if df.empty:
        issues.append("dataframe is empty")
        return issues
    if df["date"].isna().any():
        issues.append("date contains null values")
    if df["date"].duplicated().any():
        issues.append("date contains duplicate records")
    if df["date"].tolist() != sorted(df["date"].tolist()):
        issues.append("date is not sorted ascending")
    for column in ["open", "high", "low", "close"]:
        if (pd.to_numeric(df[column], errors="coerce") <= 0).any():
            issues.append(f"{column} contains non-positive values")
    if (pd.to_numeric(df["volume"], errors="coerce") < 0).any():
        issues.append("volume contains negative values")
    high_too_low = pd.to_numeric(df["high"], errors="coerce") < pd.concat(
        [pd.to_numeric(df["open"], errors="coerce"), pd.to_numeric(df["close"], errors="coerce")],
        axis=1,
    ).max(axis=1)
    if high_too_low.any():
        issues.append("high is lower than open or close in some rows")
    low_too_high = pd.to_numeric(df["low"], errors="coerce") > pd.concat(
        [pd.to_numeric(df["open"], errors="coerce"), pd.to_numeric(df["close"], errors="coerce")],
        axis=1,
    ).min(axis=1)
    if low_too_high.any():
        issues.append("low is higher than open or close in some rows")
    return issues


def _build_builtin_seed(start_date: str, end_date: str) -> pd.DataFrame:
    """生成内置种子数据。"""
    dates = pd.bdate_range(pd.to_datetime(start_date), pd.to_datetime(end_date))
    idx = np.arange(len(dates), dtype=float)
    base_close = 100.0 + idx * 0.15 + np.sin(idx / 3.0) * 0.8
    base_volume = 1_000_000.0 + idx * 3_500.0
    base_amount = base_close * base_volume
    return pd.DataFrame(
        {
            "date": dates,
            "close": base_close,
            "volume": base_volume,
            "amount": base_amount,
        }
    )


def _build_synthetic_series(base: pd.DataFrame, symbols: list[str]) -> MarketPanel:
    """基于种子数据生成合成市场面板。"""
    idx = np.arange(len(base), dtype=float)
    base_close = base["close"].to_numpy(dtype=float)
    base_volume = pd.to_numeric(base["volume"], errors="coerce").ffill().fillna(1_000_000).to_numpy(dtype=float)
    base_amount = pd.to_numeric(base["amount"], errors="coerce").ffill().fillna(
        pd.Series(base_close * base_volume, index=base.index)
    ).to_numpy(dtype=float)

    close_columns: dict[str, pd.Series] = {}
    volume_columns: dict[str, pd.Series] = {}
    amount_columns: dict[str, pd.Series] = {}
    for position, symbol in enumerate(symbols):
        offset = 0.01 * position
        slope = (position - (len(symbols) - 1) / 2.0) * 0.00025
        amplitude = 0.002 + 0.0003 * position
        phase = position * 0.7
        close_modifier = 1.0 + offset + slope * idx + amplitude * np.sin(idx / 3.0 + phase)
        close_columns[symbol] = pd.Series(base_close * close_modifier, index=base["date"], name=symbol)
        volume_modifier = 1.0 + 0.08 * position + 0.002 * idx + 0.01 * np.cos(idx / 4.0 + phase)
        volume_columns[symbol] = pd.Series(np.maximum(1000.0, base_volume * volume_modifier), index=base["date"], name=symbol)
        amount_columns[symbol] = pd.Series(
            np.maximum(1000.0, base_amount * (1.0 + 0.05 * position + 0.001 * idx)),
            index=base["date"],
            name=symbol,
        )
    close = pd.DataFrame(close_columns).sort_index()
    volume = pd.DataFrame(volume_columns).sort_index()
    amount = pd.DataFrame(amount_columns).sort_index()
    return MarketPanel(close=close, volume=volume, amount=amount, source_mode="offline-seed")


def _default_cache_root() -> Path:
    """返回默认缓存根目录。"""
    override = os.getenv(_CACHE_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[1] / _CACHE_SUBDIR


def _state_path(cache_root: Path) -> Path:
    """返回状态文件路径。"""
    return cache_root / _STATE_FILENAME


def _symbol_cache_path(cache_root: Path, symbol: str) -> Path:
    """返回单标的缓存路径。"""
    return cache_root / "symbols" / f"{symbol}.parquet"


def _parse_date(value: str | pd.Timestamp) -> pd.Timestamp:
    """把日期值转为归一化时间戳。"""
    return pd.to_datetime(value).normalize()


def _format_date(value: pd.Timestamp) -> str:
    """把日期格式化为标准字符串。"""
    return pd.Timestamp(value).normalize().strftime("%Y-%m-%d")


def _compact_date(value: pd.Timestamp) -> str:
    """把日期格式化为紧凑字符串。"""
    return pd.Timestamp(value).normalize().strftime("%Y%m%d")


def _ensure_history_frame(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
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
        raise ValueError("history frame is missing a date column")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["symbol"] = symbol
    for column in ["close", "volume", "amount"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        else:
            frame[column] = pd.NA
    frame = frame[_CACHE_COLUMNS].dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return frame


def _read_cache_frame(path: Path) -> pd.DataFrame:
    """读取缓存数据帧。"""
    if not path.exists():
        return pd.DataFrame(columns=_CACHE_COLUMNS)
    try:
        return pd.read_parquet(path)
    except ImportError as exc:
        raise RuntimeError("Parquet cache requires pyarrow or fastparquet") from exc


def _write_cache_frame(df: pd.DataFrame, path: Path) -> None:
    """写入缓存数据帧。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    try:
        df.to_parquet(tmp_path, index=False)
    except ImportError as exc:
        raise RuntimeError("Parquet cache requires pyarrow or fastparquet") from exc
    tmp_path.replace(path)


def _load_state(path: Path) -> dict[str, object]:
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


def _write_state(path: Path, payload: dict[str, object]) -> None:
    """写入缓存状态。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _missing_ranges(
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
        ranges.append((cached_end, requested_end))
    return ranges


def _merge_history_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """合并多段缓存历史。"""
    if not frames:
        return pd.DataFrame(columns=_CACHE_COLUMNS)
    merged = pd.concat(frames, ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"]).dt.normalize()
    merged["close"] = pd.to_numeric(merged["close"], errors="coerce")
    merged["volume"] = pd.to_numeric(merged["volume"], errors="coerce")
    merged["amount"] = pd.to_numeric(merged["amount"], errors="coerce")
    merged = (
        merged.sort_values("date", kind="mergesort")
        .drop_duplicates(subset=["date"], keep="last")
        .reset_index(drop=True)
    )
    return merged[_CACHE_COLUMNS]


def sync_symbol_history(
    symbol: str,
    start_date: str,
    end_date: str,
    *,
    cache_root: Path | None = None,
    fetcher: Callable[[str, str, str], pd.DataFrame] = fetch_daily_history,
    read_cache: Callable[[Path], pd.DataFrame] = _read_cache_frame,
    write_cache: Callable[[pd.DataFrame, Path], None] = _write_cache_frame,
) -> SyncResult:
    """同步单标的历史数据并更新缓存。"""
    requested_start = _parse_date(start_date)
    requested_end = _parse_date(end_date)
    if requested_start > requested_end:
        raise ValueError("start_date must be earlier than or equal to end_date")

    root = cache_root or _default_cache_root()
    cache_path = _symbol_cache_path(root, symbol)
    state_path = _state_path(root)

    raw_cached = read_cache(cache_path)
    cached_frame = _ensure_history_frame(raw_cached, symbol) if not raw_cached.empty else pd.DataFrame(columns=_CACHE_COLUMNS)
    cached_start = pd.to_datetime(cached_frame["date"]).min() if not cached_frame.empty else None
    cached_end = pd.to_datetime(cached_frame["date"]).max() if not cached_frame.empty else None
    fetch_ranges = _missing_ranges(requested_start, requested_end, cached_start, cached_end)

    fetched_frames: list[pd.DataFrame] = []
    network_hit = False
    for fetch_start, fetch_end in fetch_ranges:
        raw = fetcher(symbol, _compact_date(fetch_start), _compact_date(fetch_end))
        fetched_frames.append(_ensure_history_frame(raw, symbol))
        network_hit = True

    cache_frames = [cached_frame] if not cached_frame.empty else []
    cache_frames.extend(fetched_frames)
    merged_cache = _merge_history_frames(cache_frames)
    if not merged_cache.empty:
        write_cache(merged_cache, cache_path)

    state = _load_state(state_path)
    symbols_state = state.setdefault("symbols", {})
    source_mode = "offline-seed"
    if network_hit and not cached_frame.empty:
        source_mode = "cache+network"
    elif network_hit:
        source_mode = "network"
    elif not cached_frame.empty:
        source_mode = "cache"

    symbols_state[symbol] = {
        "cache_path": str(cache_path),
        "rows": int(len(merged_cache)),
        "requested_start": _format_date(requested_start),
        "requested_end": _format_date(requested_end),
        "cache_start": _format_date(cached_start) if cached_start is not None else None,
        "cache_end": _format_date(cached_end) if cached_end is not None else None,
        "stored_start": _format_date(pd.to_datetime(merged_cache["date"]).min()) if not merged_cache.empty else None,
        "stored_end": _format_date(pd.to_datetime(merged_cache["date"]).max()) if not merged_cache.empty else None,
        "fetched_ranges": [[_format_date(start), _format_date(end)] for start, end in fetch_ranges],
        "network_hit": network_hit,
        "cache_hit": not cached_frame.empty,
        "source_mode": source_mode,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    state["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _write_state(state_path, state)

    returned = merged_cache[
        (pd.to_datetime(merged_cache["date"]) >= requested_start)
        & (pd.to_datetime(merged_cache["date"]) <= requested_end)
    ].reset_index(drop=True)
    if returned.empty and merged_cache.empty:
        returned = pd.DataFrame(columns=_CACHE_COLUMNS)

    return SyncResult(
        frame=returned,
        cache_frame=merged_cache,
        cache_path=cache_path,
        state_path=state_path,
        cache_hit=not cached_frame.empty,
        network_hit=network_hit,
        fetched_ranges=[(_format_date(start), _format_date(end)) for start, end in fetch_ranges],
        source_mode=source_mode,
    )


def _build_market_panel(frames: list[pd.DataFrame], source_mode: str) -> MarketPanel:
    """把多标的历史拼成市场面板。"""
    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    close = combined.pivot(index="date", columns="symbol", values="close").sort_index().ffill().dropna(how="all")
    volume = combined.pivot(index="date", columns="symbol", values="volume").sort_index().ffill().dropna(how="all")
    amount = combined.pivot(index="date", columns="symbol", values="amount").sort_index().ffill().dropna(how="all")
    return MarketPanel(close=close, volume=volume, amount=amount, source_mode=source_mode)


def load_market_panel(
    symbols: list[str],
    start_date: str,
    end_date: str,
    *,
    cache_root: Path | None = None,
) -> MarketPanel:
    """加载多标的市场面板。"""
    sync_results: list[SyncResult] = []
    for symbol in symbols:
        try:
            sync_result = sync_symbol_history(
                symbol,
                start_date,
                end_date,
                cache_root=cache_root,
            )
            if sync_result.frame.empty:
                raise ValueError(f"no market data available for symbol {symbol}")
            sync_results.append(sync_result)
        except Exception:
            sync_results = []
            break

    if sync_results and len(sync_results) == len(symbols):
        frames = [result.frame for result in sync_results]
        source_modes = {result.source_mode for result in sync_results}
        if "offline-seed" in source_modes:
            source_mode = "offline-seed"
        elif "cache+network" in source_modes or ("network" in source_modes and "cache" in source_modes):
            source_mode = "cache+network"
        elif "network" in source_modes:
            source_mode = "network"
        elif "cache" in source_modes:
            source_mode = "cache"
        else:
            source_mode = "cache"
        return _build_market_panel(frames, source_mode=source_mode)

    base = _build_builtin_seed(start_date, end_date)
    return _build_synthetic_series(base, symbols)
