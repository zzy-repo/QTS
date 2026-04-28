from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx
import numpy as np
import pandas as pd
import requests
from loguru import logger

from .cache import (
    CACHE_COLUMNS,
    compact_date,
    default_cache_root,
    ensure_history_frame,
    format_date,
    load_state,
    merge_history_frames,
    missing_ranges,
    parse_date,
    read_cache_frame,
    state_path,
    symbol_cache_path,
    updated_at,
    write_cache_frame,
    write_state,
)
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


class MarketDataUnavailableError(RuntimeError):
    """表示某个标的在请求区间内没有可用市场数据。"""


SOURCE_MODE_LABELS = {
    "offline-seed": "内置合成数据",
    "cache": "本地缓存",
    "eastmoney": "东方财富",
    "tx": "腾讯行情",
    "cache+eastmoney": "本地缓存+东方财富",
    "cache+tx": "本地缓存+腾讯行情",
    "cache+network": "本地缓存+网络补拉",
    "network": "网络拉取",
}


def _build_secid(symbol: str) -> str:
    """根据股票代码构造东财历史接口的 secid。"""
    market_code = 1 if symbol.startswith("6") else 0
    return f"{market_code}.{symbol}"


def _build_tx_symbol(symbol: str) -> str:
    """把内部股票代码映射成腾讯历史接口需要的市场前缀代码。"""
    market_prefix = "sh" if symbol.startswith("6") else "sz"
    return f"{market_prefix}{symbol}"


def describe_source_mode(source_mode: str) -> str:
    """把内部来源标识转换为中文描述。"""
    return SOURCE_MODE_LABELS.get(source_mode, source_mode)


def _fetch_eastmoney_daily_history(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """通过东财接口获取单标的历史日线。"""
    logger.info("开始拉取东方财富历史行情 标的={} 开始={} 结束={}", symbol, start_date, end_date)
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": "101",
        "fqt": "1",
        "secid": _build_secid(symbol),
        "beg": start_date,
        "end": end_date,
    }
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")
    if not data or not data.get("klines"):
        raise MarketDataUnavailableError(f"东方财富未返回可用行情，标的={symbol}")
    klines = data["klines"]
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
    df.attrs["provider"] = "eastmoney"
    logger.info("东方财富历史行情拉取完成 标的={} 行数={}", symbol, len(df))
    return df


def _fetch_tx_daily_history(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """通过腾讯接口获取单标的历史日线。"""
    import akshare as ak

    logger.info("开始拉取腾讯历史行情 标的={} 开始={} 结束={}", symbol, start_date, end_date)
    tx_symbol = _build_tx_symbol(symbol)
    raw = ak.stock_zh_a_hist_tx(symbol=tx_symbol, start_date=start_date, end_date=end_date)
    if raw.empty:
        raise MarketDataUnavailableError(f"腾讯行情未返回可用行情，标的={symbol}")

    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["symbol"] = symbol
    df["open"] = pd.to_numeric(df["open"], errors="coerce")
    df["high"] = pd.to_numeric(df["high"], errors="coerce")
    df["low"] = pd.to_numeric(df["low"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["volume"] = pd.to_numeric(df["amount"], errors="coerce")
    df["amount"] = df["close"] * df["volume"]
    for column in ["amplitude", "pct_change", "change", "turnover"]:
        df[column] = pd.NA
    df = df[STANDARD_COLUMNS]
    df.attrs["provider"] = "tx"
    logger.info("腾讯历史行情拉取完成 标的={} 行数={}", symbol, len(df))
    return df


def fetch_daily_history(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """获取单标的历史日线，优先东财，失败时回退腾讯。"""
    try:
        return _fetch_eastmoney_daily_history(symbol, start_date, end_date)
    except (requests.RequestException, MarketDataUnavailableError, KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "东方财富历史行情拉取失败，回退腾讯行情 标的={} 开始={} 结束={} 异常类型={} 异常={}",
            symbol,
            start_date,
            end_date,
            type(exc).__name__,
            exc,
        )
        return _fetch_tx_daily_history(symbol, start_date, end_date)


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
        issues.append("数据为空")
        return issues
    if df["date"].isna().any():
        issues.append("日期列存在空值")
    if df["date"].duplicated().any():
        issues.append("日期列存在重复记录")
    if df["date"].tolist() != sorted(df["date"].tolist()):
        issues.append("日期列不是升序排列")
    for column in ["open", "high", "low", "close"]:
        if (pd.to_numeric(df[column], errors="coerce") <= 0).any():
            issues.append(f"{column} 列存在非正数")
    if (pd.to_numeric(df["volume"], errors="coerce") < 0).any():
        issues.append("volume 列存在负数")
    high_too_low = pd.to_numeric(df["high"], errors="coerce") < pd.concat(
        [pd.to_numeric(df["open"], errors="coerce"), pd.to_numeric(df["close"], errors="coerce")],
        axis=1,
    ).max(axis=1)
    if high_too_low.any():
        issues.append("部分记录的 high 小于 open 或 close")
    low_too_high = pd.to_numeric(df["low"], errors="coerce") > pd.concat(
        [pd.to_numeric(df["open"], errors="coerce"), pd.to_numeric(df["close"], errors="coerce")],
        axis=1,
    ).min(axis=1)
    if low_too_high.any():
        issues.append("部分记录的 low 大于 open 或 close")
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


def sync_symbol_history(
    symbol: str,
    start_date: str,
    end_date: str,
    *,
    cache_root: Path | None = None,
    fetcher: Callable[[str, str, str], pd.DataFrame] = fetch_daily_history,
    read_cache: Callable[[Path], pd.DataFrame] = read_cache_frame,
    write_cache: Callable[[pd.DataFrame, Path], None] = write_cache_frame,
) -> SyncResult:
    """同步单标的历史数据并更新缓存。"""
    requested_start = parse_date(start_date)
    requested_end = parse_date(end_date)
    if requested_start > requested_end:
        raise ValueError("开始日期不能晚于结束日期")

    root = cache_root or default_cache_root()
    cache_path = symbol_cache_path(root, symbol)
    state_file = state_path(root)

    raw_cached = read_cache(cache_path)
    cached_frame = ensure_history_frame(raw_cached, symbol) if not raw_cached.empty else pd.DataFrame(columns=CACHE_COLUMNS)
    cached_start = pd.to_datetime(cached_frame["date"]).min() if not cached_frame.empty else None
    cached_end = pd.to_datetime(cached_frame["date"]).max() if not cached_frame.empty else None
    fetch_ranges = missing_ranges(requested_start, requested_end, cached_start, cached_end)
    logger.info(
        "开始同步 标的={} 请求区间=[{}, {}] 命中缓存={} 缓存开始={} 缓存结束={} 待拉取区间={}",
        symbol,
        format_date(requested_start),
        format_date(requested_end),
        not cached_frame.empty,
        format_date(cached_start),
        format_date(cached_end),
        [(format_date(start), format_date(end)) for start, end in fetch_ranges],
    )

    fetched_frames: list[pd.DataFrame] = []
    network_hit = False
    network_source_mode = "network"
    for fetch_start, fetch_end in fetch_ranges:
        raw = fetcher(symbol, compact_date(fetch_start), compact_date(fetch_end))
        provider = str(raw.attrs.get("provider", "")).strip().lower()
        if provider == "tx":
            network_source_mode = "network-tx"
        elif provider == "eastmoney":
            network_source_mode = "network-eastmoney"
        fetched_frames.append(ensure_history_frame(raw, symbol))
        network_hit = True
        logger.info(
            "区间拉取完成 标的={} 来源={}({}) 区间=[{}, {}] 行数={}",
            symbol,
            describe_source_mode("tx" if provider == "tx" else "eastmoney" if provider == "eastmoney" else provider or "network"),
            provider or "unknown",
            format_date(fetch_start),
            format_date(fetch_end),
            len(raw),
        )

    cache_frames = [cached_frame] if not cached_frame.empty else []
    cache_frames.extend(fetched_frames)
    merged_cache = merge_history_frames(cache_frames)
    if not merged_cache.empty:
        write_cache(merged_cache, cache_path)

    state = load_state(state_file)
    timestamp = updated_at()
    symbols_state = state.setdefault("symbols", {})
    source_mode = "offline-seed"
    if network_hit and not cached_frame.empty:
        source_mode = f"cache+{network_source_mode}"
    elif network_hit:
        source_mode = network_source_mode
    elif not cached_frame.empty:
        source_mode = "cache"

    symbols_state[symbol] = {
        "cache_path": str(cache_path),
        "rows": int(len(merged_cache)),
        "requested_start": format_date(requested_start),
        "requested_end": format_date(requested_end),
        "cache_start": format_date(cached_start) if cached_start is not None else None,
        "cache_end": format_date(cached_end) if cached_end is not None else None,
        "stored_start": format_date(pd.to_datetime(merged_cache["date"]).min()) if not merged_cache.empty else None,
        "stored_end": format_date(pd.to_datetime(merged_cache["date"]).max()) if not merged_cache.empty else None,
        "fetched_ranges": [[format_date(start), format_date(end)] for start, end in fetch_ranges],
        "network_hit": network_hit,
        "cache_hit": not cached_frame.empty,
        "source_mode": source_mode,
        "updated_at": timestamp,
    }
    state["updated_at"] = timestamp
    write_state(state_file, state)

    returned = merged_cache[
        (pd.to_datetime(merged_cache["date"]) >= requested_start)
        & (pd.to_datetime(merged_cache["date"]) <= requested_end)
    ].reset_index(drop=True)
    if returned.empty and merged_cache.empty:
        returned = pd.DataFrame(columns=CACHE_COLUMNS)
    logger.info(
        "同步完成 标的={} 数据来源={}({}) 返回行数={} 缓存行数={}",
        symbol,
        describe_source_mode(source_mode),
        source_mode,
        len(returned),
        len(merged_cache),
    )

    return SyncResult(
        frame=returned,
        cache_frame=merged_cache,
        cache_path=cache_path,
        state_path=state_file,
        cache_hit=not cached_frame.empty,
        network_hit=network_hit,
        fetched_ranges=[(format_date(start), format_date(end)) for start, end in fetch_ranges],
        source_mode=source_mode,
    )


def _build_market_panel(frames: list[pd.DataFrame], source_mode: str) -> MarketPanel:
    """把多标的历史拼成市场面板。"""
    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    close = combined.pivot(index="date", columns="symbol", values="close").sort_index()
    volume = combined.pivot(index="date", columns="symbol", values="volume").sort_index()
    amount = combined.pivot(index="date", columns="symbol", values="amount").sort_index()
    complete_mask = close.notna().all(axis=1) & volume.notna().all(axis=1) & amount.notna().all(axis=1)
    close = close.loc[complete_mask]
    volume = volume.loc[complete_mask]
    amount = amount.loc[complete_mask]
    return MarketPanel(close=close, volume=volume, amount=amount, source_mode=source_mode)


def _resolve_panel_source_mode(sync_results: list[SyncResult]) -> str:
    """把多标的同步来源聚合成统一面板来源。"""
    source_modes = {result.source_mode for result in sync_results}
    if "offline-seed" in source_modes:
        return "offline-seed"
    if any(mode.startswith("cache+network-tx") for mode in source_modes):
        return "cache+tx"
    if any(mode.startswith("cache+network-eastmoney") for mode in source_modes):
        return "cache+eastmoney"
    if any(mode.startswith("network-tx") for mode in source_modes):
        return "tx"
    if any(mode.startswith("network-eastmoney") for mode in source_modes):
        return "eastmoney"
    if "cache+network" in source_modes or ("network" in source_modes and "cache" in source_modes):
        return "cache+network"
    if "network" in source_modes:
        return "network"
    if "cache" in source_modes:
        return "cache"
    return "cache"


def load_market_panel(
    symbols: list[str],
    start_date: str,
    end_date: str,
    *,
    cache_root: Path | None = None,
    allow_synthetic_fallback: bool = False,
) -> MarketPanel:
    """加载多标的市场面板。"""
    logger.info(
        "开始加载市场面板 标的={} 开始={} 结束={} 缓存目录={} 允许合成回退={}",
        symbols,
        start_date,
        end_date,
        cache_root,
        allow_synthetic_fallback,
    )
    sync_results: list[SyncResult] = []
    try:
        for symbol in symbols:
            try:
                sync_result = sync_symbol_history(
                    symbol,
                    start_date,
                    end_date,
                    cache_root=cache_root,
                )
            except (httpx.HTTPError, requests.RequestException):
                if allow_synthetic_fallback:
                    logger.warning("市场面板加载遇到网络异常，回退到合成数据 标的={}", symbols)
                    base = _build_builtin_seed(start_date, end_date)
                    return _build_synthetic_series(base, symbols)
                raise
            if sync_result.frame.empty:
                raise MarketDataUnavailableError(f"标的无可用行情数据：{symbol}")
            sync_results.append(sync_result)
    except MarketDataUnavailableError:
        if allow_synthetic_fallback:
            logger.warning("市场面板加载无可用数据，回退到合成数据 标的={}", symbols)
            base = _build_builtin_seed(start_date, end_date)
            return _build_synthetic_series(base, symbols)
        raise

    if sync_results and len(sync_results) == len(symbols):
        frames = [result.frame for result in sync_results]
        source_mode = _resolve_panel_source_mode(sync_results)
        panel = _build_market_panel(frames, source_mode=source_mode)
        if panel.close.empty:
            if allow_synthetic_fallback:
                logger.warning("市场面板没有完整截面数据，回退到合成数据 标的={}", symbols)
                base = _build_builtin_seed(start_date, end_date)
                return _build_synthetic_series(base, symbols)
            raise MarketDataUnavailableError("没有可用的完整市场截面数据")
        logger.info(
            "市场面板加载完成 数据来源={}({}) 行数={} 标的={}",
            describe_source_mode(panel.source_mode),
            panel.source_mode,
            len(panel.close),
            list(panel.close.columns),
        )
        return panel

    if allow_synthetic_fallback:
        logger.warning("市场面板不完整，回退到合成数据 标的={}", symbols)
        base = _build_builtin_seed(start_date, end_date)
        return _build_synthetic_series(base, symbols)
    raise MarketDataUnavailableError("无法基于请求标的构建市场面板")
