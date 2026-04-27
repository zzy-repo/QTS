from __future__ import annotations

from pathlib import Path

import httpx
import pandas as pd

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
    if "date" not in normalized.columns and "日期" in normalized.columns:
        normalized = normalized.rename(columns=RAW_COLUMN_MAP)
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
        [
            pd.to_numeric(df["open"], errors="coerce"),
            pd.to_numeric(df["close"], errors="coerce"),
        ],
        axis=1,
    ).max(axis=1)
    if high_too_low.any():
        issues.append("high is lower than open or close in some rows")
    low_too_high = pd.to_numeric(df["low"], errors="coerce") > pd.concat(
        [
            pd.to_numeric(df["open"], errors="coerce"),
            pd.to_numeric(df["close"], errors="coerce"),
        ],
        axis=1,
    ).min(axis=1)
    if low_too_high.any():
        issues.append("low is higher than open or close in some rows")
    return issues
