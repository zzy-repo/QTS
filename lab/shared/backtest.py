from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from .data_source import fetch_daily_history

WeightScheme = Literal["equal", "inv_vol"]


@dataclass(frozen=True)
class PortfolioRun:
    holdings: pd.DataFrame
    pnl: pd.DataFrame
    equity: pd.DataFrame


@dataclass(frozen=True)
class MarketPanel:
    close: pd.DataFrame
    volume: pd.DataFrame
    amount: pd.DataFrame
    source_mode: str


def _seed_history_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / name / "artifacts" / "history.csv"


def _load_seed_base() -> pd.DataFrame:
    candidates = [
        Path(__file__).resolve().parents[1] / "07-直连采集" / "artifacts" / "history.csv",
        Path(__file__).resolve().parents[1] / "01-增量更新" / "artifacts" / "merged.csv",
        Path(__file__).resolve().parents[1] / "00-数据源连通性" / "artifacts" / "source.csv",
    ]
    frames: list[pd.DataFrame] = []
    for path in candidates:
        if path.exists():
            frame = pd.read_csv(path)
            if "date" in frame.columns and "close" in frame.columns:
                selected = frame.copy()
                rename_map = {
                    "日期": "date",
                    "收盘": "close",
                    "成交量": "volume",
                    "成交额": "amount",
                }
                selected = selected.rename(columns=rename_map)
                columns = ["date", "close"]
                for extra in ["volume", "amount"]:
                    if extra in selected.columns:
                        columns.append(extra)
                selected = selected[columns].copy()
                frames.append(selected)
    if not frames:
        raise FileNotFoundError("no seed history available for offline panel")
    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    combined["close"] = pd.to_numeric(combined["close"], errors="coerce")
    if "volume" in combined.columns:
        combined["volume"] = pd.to_numeric(combined["volume"], errors="coerce")
    else:
        combined["volume"] = np.nan
    if "amount" in combined.columns:
        combined["amount"] = pd.to_numeric(combined["amount"], errors="coerce")
    else:
        combined["amount"] = np.nan
    combined = combined.dropna(subset=["date", "close"])
    return (
        combined.sort_values("date")
        .drop_duplicates(subset=["date"], keep="last")
        .reset_index(drop=True)
    )


def _build_synthetic_series(
    base: pd.DataFrame,
    symbols: list[str],
) -> MarketPanel:
    idx = np.arange(len(base), dtype=float)
    close_columns: dict[str, pd.Series] = {}
    volume_columns: dict[str, pd.Series] = {}
    amount_columns: dict[str, pd.Series] = {}
    base_close = base["close"].to_numpy(dtype=float)
    if "volume" in base.columns and base["volume"].notna().any():
        base_volume = pd.to_numeric(base["volume"], errors="coerce").ffill().fillna(1_000_000).to_numpy(dtype=float)
    else:
        base_volume = np.full(len(base), 1_000_000.0)
    if "amount" in base.columns and base["amount"].notna().any():
        amount_series = pd.to_numeric(base["amount"], errors="coerce").ffill()
        base_amount = amount_series.fillna(pd.Series(base_close * base_volume, index=base.index)).to_numpy(dtype=float)
    else:
        base_amount = base_close * base_volume

    for position, symbol in enumerate(symbols):
        offset = 0.01 * position
        slope = (position - (len(symbols) - 1) / 2.0) * 0.00025
        amplitude = 0.002 + 0.0003 * position
        phase = position * 0.7
        close_modifier = 1.0 + offset + slope * idx + amplitude * np.sin(idx / 3.0 + phase)
        close_series = pd.Series(base_close * close_modifier, index=base["date"], name=symbol)

        volume_modifier = 1.0 + 0.08 * position + 0.002 * idx + 0.01 * np.cos(idx / 4.0 + phase)
        volume_series = pd.Series(
            np.maximum(1000.0, base_volume * volume_modifier),
            index=base["date"],
            name=symbol,
        )
        amount_series = pd.Series(
            np.maximum(1000.0, base_amount * (1.0 + 0.05 * position + 0.001 * idx)),
            index=base["date"],
            name=symbol,
        )
        close_columns[symbol] = close_series
        volume_columns[symbol] = volume_series
        amount_columns[symbol] = amount_series

    close = pd.DataFrame(close_columns).sort_index()
    volume = pd.DataFrame(volume_columns).sort_index()
    amount = pd.DataFrame(amount_columns).sort_index()
    return MarketPanel(close=close, volume=volume, amount=amount, source_mode="offline-seed")


def _expand_seed_base(base: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    business_index = pd.bdate_range(start=pd.to_datetime(start_date), end=pd.to_datetime(end_date))
    if business_index.empty:
        return base.copy()
    ordered = base.sort_values("date").reset_index(drop=True)
    if len(ordered) == 1:
        close = np.full(len(business_index), float(ordered.loc[0, "close"]))
        volume = np.full(len(business_index), float(ordered.loc[0, "volume"]))
        amount = np.full(len(business_index), float(ordered.loc[0, "amount"]))
    else:
        source_x = np.linspace(0.0, 1.0, len(ordered))
        target_x = np.linspace(0.0, 1.0, len(business_index))
        close = np.interp(target_x, source_x, ordered["close"].to_numpy(dtype=float))
        volume = np.interp(target_x, source_x, ordered["volume"].to_numpy(dtype=float))
        amount = np.interp(target_x, source_x, ordered["amount"].to_numpy(dtype=float))
    return pd.DataFrame(
        {
            "date": business_index,
            "close": close,
            "volume": volume,
            "amount": amount,
        }
    )


def load_close_panel(
    symbols: list[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    market = load_market_panel(symbols, start_date, end_date)
    return market.close


def load_market_panel(
    symbols: list[str],
    start_date: str,
    end_date: str,
) -> MarketPanel:
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

    base = _load_seed_base()
    base = base[
        (base["date"] >= pd.to_datetime(start_date))
        & (base["date"] <= pd.to_datetime(end_date))
    ].reset_index(drop=True)
    if base.empty:
        base = _load_seed_base()
    if len(base) < 120:
        base = _expand_seed_base(base, start_date, end_date)
    market = _build_synthetic_series(base, symbols)
    return market


def _rebalance_weights(
    momentum_row: pd.Series,
    vol_row: pd.Series,
    top_n: int,
    scheme: WeightScheme,
) -> pd.Series:
    ranked = momentum_row.dropna().sort_values(ascending=False)
    selected = ranked.head(top_n)
    if selected.empty:
        return pd.Series(dtype=float)
    if scheme == "equal":
        weights = pd.Series(1.0 / len(selected), index=selected.index)
    else:
        vols = vol_row.reindex(selected.index).replace(0, np.nan).dropna()
        if vols.empty:
            weights = pd.Series(1.0 / len(selected), index=selected.index)
        else:
            inv = 1.0 / vols
            weights = inv / inv.sum()
            weights = weights.reindex(selected.index).fillna(0.0)
            total = weights.sum()
            if total > 0:
                weights = weights / total
            else:
                weights = pd.Series(1.0 / len(selected), index=selected.index)
    weights.name = "weight"
    return weights.sort_values(ascending=False)


def build_momentum_portfolio(
    panel: pd.DataFrame,
    lookback: int = 20,
    top_n: int = 3,
    scheme: WeightScheme = "equal",
) -> PortfolioRun:
    close = panel.copy()
    daily_ret = close.pct_change()
    momentum = close.pct_change(lookback)
    rolling_vol = daily_ret.rolling(lookback).std()

    holdings_rows: list[dict[str, object]] = []
    pnl_rows: list[dict[str, object]] = []
    equity = 1.0
    equity_rows: list[dict[str, object]] = []
    prev_weights = pd.Series(dtype=float)

    dates = list(close.index)
    for idx in range(lookback, len(dates) - 1):
        signal_date = dates[idx]
        next_date = dates[idx + 1]
        mom_row = momentum.loc[signal_date]
        vol_row = rolling_vol.loc[signal_date]
        weights = _rebalance_weights(mom_row, vol_row, top_n=top_n, scheme=scheme)
        if weights.empty:
            continue

        realized = daily_ret.loc[next_date].reindex(weights.index)
        realized = realized.fillna(0.0)
        gross_return = float((weights * realized).sum())
        turnover = float(weights.sub(prev_weights, fill_value=0.0).abs().sum())
        pnl_rows.append(
            {
                "date": next_date.strftime("%Y-%m-%d"),
                "signal_date": signal_date.strftime("%Y-%m-%d"),
                "gross_return": gross_return,
                "turnover": turnover,
            }
        )

        for rank, (symbol, weight) in enumerate(weights.items(), start=1):
            holdings_rows.append(
                {
                    "date": next_date.strftime("%Y-%m-%d"),
                    "signal_date": signal_date.strftime("%Y-%m-%d"),
                    "symbol": symbol,
                    "weight": float(weight),
                    "rank": rank,
                    "momentum": float(mom_row.get(symbol, np.nan)),
                    "volatility": float(vol_row.get(symbol, np.nan)),
                }
            )

        equity *= 1.0 + gross_return
        equity_rows.append(
            {
                "date": next_date.strftime("%Y-%m-%d"),
                "equity": equity,
            }
        )
        prev_weights = weights

    holdings = pd.DataFrame(holdings_rows)
    pnl = pd.DataFrame(pnl_rows)
    equity_df = pd.DataFrame(equity_rows)
    if not pnl.empty:
        pnl["equity"] = equity_df["equity"].values
        pnl["cum_return"] = pnl["equity"] - 1.0
    return PortfolioRun(holdings=holdings, pnl=pnl, equity=equity_df)


def apply_costs(pnl: pd.DataFrame, fee_bps: float, slippage_bps: float) -> pd.DataFrame:
    if pnl.empty:
        return pnl.copy()
    cost_rate = (fee_bps + slippage_bps) / 10000.0
    out = pnl.copy()
    if "slippage_cost" in out.columns and "equity_before" in out.columns:
        out["cost"] = pd.to_numeric(out["slippage_cost"], errors="coerce") / pd.to_numeric(
            out["equity_before"], errors="coerce"
        ).replace(0, np.nan)
    else:
        out["cost"] = pd.to_numeric(out["turnover"], errors="coerce") * cost_rate
    out["cost"] = out["cost"].fillna(0.0)
    out["net_return"] = out["gross_return"] - out["cost"]
    equity = 1.0
    net_equity: list[float] = []
    for value in out["net_return"]:
        equity *= 1.0 + float(value)
        net_equity.append(equity)
    out["net_equity"] = net_equity
    out["net_cum_return"] = out["net_equity"] - 1.0
    return out


def compute_metrics(returns: pd.Series) -> pd.DataFrame:
    series = pd.Series(returns)
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return pd.DataFrame(
            [
                {
                    "sharpe": np.nan,
                    "mdd": np.nan,
                    "volatility": np.nan,
                    "annualized_return": np.nan,
                }
            ]
        )
    ann_factor = np.sqrt(252)
    vol = float(clean.std(ddof=0) * ann_factor)
    sharpe = float((clean.mean() / clean.std(ddof=0) * ann_factor) if clean.std(ddof=0) else np.nan)
    equity = (1.0 + clean).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    mdd = float(drawdown.min())
    total_return = float(equity.iloc[-1] - 1.0)
    annualized = float((1.0 + total_return) ** (252 / len(clean)) - 1.0) if len(clean) else np.nan
    return pd.DataFrame(
        [
            {
                "sharpe": sharpe,
                "mdd": mdd,
                "volatility": vol,
                "annualized_return": annualized,
            }
        ]
    )
