from __future__ import annotations

import numpy as np
import pandas as pd

from qts.core.analysis import risk_state_machine

from .backtest import MarketPanel


def build_ohlcv_frame(market: MarketPanel) -> pd.DataFrame:
    close = market.close.stack().rename("close")
    volume = market.volume.stack().rename("volume")
    amount = market.amount.stack().rename("amount")
    frame = pd.concat([close, volume, amount], axis=1).reset_index()
    frame.columns = ["date", "symbol", "close", "volume", "amount"]
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    frame["open"] = frame.groupby("symbol")["close"].shift(1).fillna(frame["close"])
    frame["high"] = frame[["open", "close"]].max(axis=1) * 1.01
    frame["low"] = frame[["open", "close"]].min(axis=1) * 0.99
    return frame[["symbol", "date", "open", "high", "low", "close", "volume", "amount"]]


def audit_alignment(frame: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    required = {"signal_date", "trade_date", "pnl_date"}
    if not required.issubset(frame.columns):
        missing = sorted(required - set(frame.columns))
        return [f"missing columns: {', '.join(missing)}"]
    signal = pd.to_datetime(frame["signal_date"])
    trade = pd.to_datetime(frame["trade_date"])
    pnl = pd.to_datetime(frame["pnl_date"])
    if not (signal < trade).all():
        issues.append("signal_date is not strictly earlier than trade_date")
    if not (trade < pnl).all():
        issues.append("trade_date is not strictly earlier than pnl_date")
    key_columns = ["signal_date", "trade_date", "pnl_date"]
    if "symbol" in frame.columns:
        key_columns.append("symbol")
    if frame.duplicated(subset=key_columns).any():
        issues.append("alignment records contain duplicates")
    return issues


def covariance_regularization(returns: pd.DataFrame, shrinkage: float = 0.15) -> dict[str, object]:
    clean = returns.apply(pd.to_numeric, errors="coerce").dropna(how="all")
    clean = clean.dropna(axis=0, how="any")
    if clean.empty:
        raise ValueError("returns are empty after cleaning")
    sample = clean.cov().to_numpy(dtype=float)
    diag = np.diag(np.diag(sample))
    shrunk = (1.0 - shrinkage) * sample + shrinkage * diag
    raw_eig = np.linalg.eigvalsh(sample)
    shrunk_eig = np.linalg.eigvalsh(shrunk)
    raw_cond = float(np.linalg.cond(sample))
    shrunk_cond = float(np.linalg.cond(shrunk))
    return {
        "raw_cov": pd.DataFrame(sample, index=clean.columns, columns=clean.columns),
        "shrunk_cov": pd.DataFrame(shrunk, index=clean.columns, columns=clean.columns),
        "raw_min_eig": float(raw_eig.min()),
        "shrunk_min_eig": float(shrunk_eig.min()),
        "raw_condition": raw_cond,
        "shrunk_condition": shrunk_cond,
    }

