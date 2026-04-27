from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import json

import numpy as np
import pandas as pd

from bootstrap import ROOT
from qts.config import QTSConfig, build_system_from_config, load_qts_config
from qts.data_source import SyncResult, sync_symbol_history
from qts.models import MarketPanel

SIGNAL_COLUMNS = ["date", "symbol", "rank", "score", "weight"]
CACHE_COLUMNS = ["date", "symbol", "close", "volume", "amount"]


@dataclass(frozen=True)
class EntryRun:
    name: str
    config_path: Path
    config: QTSConfig
    market: MarketPanel
    result: object
    signals: pd.DataFrame
    report: pd.DataFrame


def default_artifact_dir() -> Path:
    path = ROOT / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_cache_root() -> Path:
    return default_artifact_dir() / "cache"


def resolve_config_path(default_name: str, config_path: str | Path | None = None) -> Path:
    if config_path is None:
        return ROOT / default_name
    return Path(config_path)


def _cache_csv_path(cache_path: Path) -> Path:
    return cache_path.with_suffix(".csv")


def _read_cache_csv(path: Path) -> pd.DataFrame:
    csv_path = _cache_csv_path(path)
    if not csv_path.exists():
        return pd.DataFrame(columns=CACHE_COLUMNS)
    frame = pd.read_csv(csv_path)
    for column in CACHE_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame[CACHE_COLUMNS]


def _write_cache_csv(frame: pd.DataFrame, path: Path) -> None:
    csv_path = _cache_csv_path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame[CACHE_COLUMNS].to_csv(csv_path, index=False)


def fake_fetch_daily_history(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    dates = pd.bdate_range(pd.to_datetime(start_date), pd.to_datetime(end_date))
    idx = np.arange(len(dates), dtype=float)
    seed = sum(ord(ch) for ch in symbol)
    base = 20.0 + float(seed % 31)
    slope = 0.18 + (seed % 5) * 0.03
    phase = (seed % 13) / 4.0
    close = base + idx * slope + np.sin(idx / 4.0 + phase) * (0.6 + (seed % 7) * 0.08)
    open_ = close * (1.0 - 0.002 + 0.0002 * phase)
    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    volume = 500_000.0 + idx * (1_500.0 + (seed % 4) * 120.0)
    amount = close * volume
    pct_change = pd.Series(close).pct_change().fillna(0.0) * 100.0
    change = pd.Series(close - open_).fillna(0.0)
    turnover = 0.5 + 0.01 * phase + idx * 0.002
    return pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "amount": amount,
            "amplitude": (high / low - 1.0) * 100.0,
            "pct_change": pct_change.to_numpy(),
            "change": change.to_numpy(),
            "turnover": turnover,
            "symbol": symbol,
        }
    )


def load_market_panel_with_cache(
    config: QTSConfig,
    *,
    cache_root: Path | None = None,
    fetcher: Callable[[str, str, str], pd.DataFrame] = fake_fetch_daily_history,
) -> tuple[MarketPanel, list[SyncResult]]:
    root = cache_root or default_cache_root()
    sync_results: list[SyncResult] = []
    for symbol in config.market.symbols:
        sync_result = sync_symbol_history(
            symbol,
            config.market.start_date,
            config.market.end_date,
            cache_root=root,
            fetcher=fetcher,
            read_cache=_read_cache_csv,
            write_cache=_write_cache_csv,
        )
        if sync_result.frame.empty:
            raise ValueError(f"no market data available for symbol {symbol}")
        sync_results.append(sync_result)

    frames = [result.frame.copy() for result in sync_results]
    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    close = combined.pivot(index="date", columns="symbol", values="close").sort_index().ffill().dropna(how="all")
    volume = combined.pivot(index="date", columns="symbol", values="volume").sort_index().ffill().dropna(how="all")
    amount = combined.pivot(index="date", columns="symbol", values="amount").sort_index().ffill().dropna(how="all")

    source_modes = {result.source_mode for result in sync_results}
    if "cache+network" in source_modes:
        source_mode = "cache+network"
    elif "network" in source_modes and "cache" in source_modes:
        source_mode = "cache+network"
    elif "network" in source_modes:
        source_mode = "network"
    elif "cache" in source_modes:
        source_mode = "cache"
    else:
        source_mode = "offline-seed"

    return MarketPanel(close=close, volume=volume, amount=amount, source_mode=source_mode), sync_results


def run_configured_system(
    config_path: str | Path | None,
    default_name: str,
    *,
    cache_root: Path | None = None,
) -> tuple[Path, QTSConfig, MarketPanel, object, pd.DataFrame]:
    resolved = resolve_config_path(default_name, config_path)
    config = load_qts_config(resolved)
    market, sync_results = load_market_panel_with_cache(config, cache_root=cache_root)
    system = build_system_from_config(config)
    result = system.run(market)
    signals = normalize_signal_frame(result.strategy_signals)
    signals.attrs["cache_results"] = sync_results
    return resolved, config, market, result, signals


def normalize_signal_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in SIGNAL_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = pd.NA
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.strftime("%Y-%m-%d")
    normalized["symbol"] = normalized["symbol"].astype(str)
    normalized["rank"] = pd.to_numeric(normalized["rank"], errors="coerce").astype("Int64")
    normalized["score"] = pd.to_numeric(normalized["score"], errors="coerce")
    normalized["weight"] = pd.to_numeric(normalized["weight"], errors="coerce")
    ordered_columns = SIGNAL_COLUMNS + [column for column in normalized.columns if column not in SIGNAL_COLUMNS]
    normalized = normalized[ordered_columns]
    return normalized.sort_values(["date", "rank", "symbol"], kind="mergesort").reset_index(drop=True)


def latest_signal_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = normalize_signal_frame(frame)
    if normalized.empty:
        return normalized
    latest_date = normalized["date"].max()
    return normalized[normalized["date"].eq(latest_date)].copy().reset_index(drop=True)


def enrich_with_pnl(signals: pd.DataFrame, pnl: pd.DataFrame) -> pd.DataFrame:
    frame = normalize_signal_frame(signals)
    if pnl.empty:
        return frame
    pnl_frame = pnl.copy()
    pnl_frame["date"] = pd.to_datetime(pnl_frame["date"]).dt.strftime("%Y-%m-%d")
    keep_columns = [column for column in ["date", "gross_return", "turnover", "slippage_cost", "equity", "cum_return"] if column in pnl_frame.columns]
    if not keep_columns:
        return frame
    return frame.merge(pnl_frame[keep_columns], on="date", how="left")


def signals_to_json_ready(frame: pd.DataFrame) -> list[dict[str, object]]:
    normalized = normalize_signal_frame(frame)
    payload = normalized.where(pd.notna(normalized), None)
    return json.loads(payload.to_json(orient="records", force_ascii=False))


def save_frame(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def save_json_payload(payload: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

