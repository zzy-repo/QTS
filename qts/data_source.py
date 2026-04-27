from __future__ import annotations

import numpy as np
import httpx
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


def fetch_daily_history(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
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
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def quality_checks(df: pd.DataFrame) -> list[str]:
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
    idx = np.arange(len(base), dtype=float)
    base_close = base["close"].to_numpy(dtype=float)
    base_volume = pd.to_numeric(base["volume"], errors="coerce").ffill().fillna(1_000_000).to_numpy(dtype=float)
    base_amount = pd.to_numeric(base["amount"], errors="coerce").ffill().fillna(pd.Series(base_close * base_volume, index=base.index)).to_numpy(dtype=float)

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
        amount_columns[symbol] = pd.Series(np.maximum(1000.0, base_amount * (1.0 + 0.05 * position + 0.001 * idx)), index=base["date"], name=symbol)
    close = pd.DataFrame(close_columns).sort_index()
    volume = pd.DataFrame(volume_columns).sort_index()
    amount = pd.DataFrame(amount_columns).sort_index()
    return MarketPanel(close=close, volume=volume, amount=amount, source_mode="offline-seed")


def load_market_panel(symbols: list[str], start_date: str, end_date: str) -> MarketPanel:
    frames: list[pd.DataFrame] = []
    network_ok = True
    try:
        for symbol in symbols:
            raw = fetch_daily_history(symbol, start_date, end_date).copy()
            raw["close"] = pd.to_numeric(raw["close"], errors="coerce")
            raw["volume"] = pd.to_numeric(raw["volume"], errors="coerce")
            raw["amount"] = pd.to_numeric(raw["amount"], errors="coerce")
            raw["date"] = pd.to_datetime(raw["date"])
            frames.append(raw[["date", "symbol", "close", "volume", "amount"]])
    except Exception:
        network_ok = False
    if network_ok and frames:
        combined = pd.concat(frames, ignore_index=True)
        close = combined.pivot(index="date", columns="symbol", values="close").sort_index().ffill().dropna(how="all")
        volume = combined.pivot(index="date", columns="symbol", values="volume").sort_index().ffill().dropna(how="all")
        amount = combined.pivot(index="date", columns="symbol", values="amount").sort_index().ffill().dropna(how="all")
        return MarketPanel(close=close, volume=volume, amount=amount, source_mode="network")

    base = _build_builtin_seed(start_date, end_date)
    return _build_synthetic_series(base, symbols)
