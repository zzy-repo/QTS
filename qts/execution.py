from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from .models import ExecutionRun, MarketPanel


def _annualized_return(total_return: float, periods: int, trading_days_per_year: int = 252) -> float:
    """计算执行结果的年化收益。"""
    if periods <= 0:
        return float("nan")
    base = 1.0 + float(total_return)
    if base <= 0:
        return float("nan")
    return float(base ** (trading_days_per_year / float(periods)) - 1.0)


def dynamic_slippage_cost(
    trade_notional: float,
    adv_notional: float,
    volatility: float,
    base_bps: float = 1.0,
    participation_scale: float = 0.035,
    vol_scale: float = 0.15,
) -> float:
    """估算动态滑点成本。"""
    if trade_notional <= 0 or adv_notional <= 0:
        return 0.0
    participation = trade_notional / adv_notional
    rate = base_bps / 10000.0
    rate += participation_scale * np.sqrt(participation)
    rate += vol_scale * max(volatility, 0.0)
    return float(trade_notional * rate)


def execute_rebalance(
    target_holdings: pd.DataFrame,
    market: MarketPanel,
    initial_cash: float = 1_000_000.0,
    lot_size: int = 100,
    max_adv_pct: float | None = None,
    slippage_fn: Callable[[float, float, float], float] | None = None,
    tradable_mask: pd.DataFrame | None = None,
) -> ExecutionRun:
    """执行目标持仓再平衡。"""
    target_holdings = target_holdings.copy()
    target_holdings["date"] = pd.to_datetime(target_holdings["date"], format="mixed")
    dates = sorted(target_holdings["date"].unique())
    prev_shares = pd.Series(dtype=float)
    cash = float(initial_cash)
    orders_rows: list[dict[str, object]] = []
    holdings_rows: list[dict[str, object]] = []
    pnl_rows: list[dict[str, object]] = []
    daily_returns = market.close.pct_change()

    for i, date in enumerate(dates):
        date_ts = pd.Timestamp(date)
        price_row = market.close.loc[date_ts]
        amount_row = market.amount.loc[date_ts]
        vol_row = daily_returns.rolling(20, min_periods=1).std().loc[date_ts]
        target_row = target_holdings.loc[target_holdings["date"] == date_ts].set_index("symbol")
        target_weights = target_row["weight"].astype(float)
        if target_weights.sum() > 0:
            target_weights = target_weights / target_weights.sum()
        current_prev = prev_shares.reindex(price_row.index).fillna(0.0)
        if tradable_mask is not None and date_ts in tradable_mask.index:
            tradable_row = tradable_mask.loc[date_ts].reindex(price_row.index).fillna(True).astype(bool)
        else:
            tradable_row = pd.Series(True, index=price_row.index)
        portfolio_value_before = float(cash + (current_prev * price_row).sum())
        target_notional = target_weights * portfolio_value_before
        desired_shares = target_notional.reindex(price_row.index).fillna(0.0) / price_row
        target_shares = np.floor(desired_shares / lot_size) * lot_size
        if max_adv_pct is not None:
            max_trade = np.floor((market.volume.loc[date_ts] * max_adv_pct) / lot_size) * lot_size
            proposed_trade = target_shares.sub(current_prev, fill_value=0.0)
            clipped_trade = proposed_trade.clip(lower=-max_trade, upper=max_trade)
            target_shares = current_prev + clipped_trade
            target_shares = np.floor(target_shares / lot_size) * lot_size
        blocked_symbols = tradable_row[~tradable_row].index.tolist()
        if blocked_symbols:
            target_shares = target_shares.copy()
            target_shares.loc[blocked_symbols] = current_prev.loc[blocked_symbols]
        trade_shares = target_shares.sub(current_prev, fill_value=0.0)
        trade_notional = (trade_shares.abs() * price_row).fillna(0.0)
        target_values = target_shares.reindex(price_row.index).fillna(0.0).to_numpy(dtype=float)
        desired_values = desired_shares.reindex(price_row.index).fillna(0.0).to_numpy(dtype=float)
        fill_ratio = np.divide(target_values, desired_values, out=np.ones_like(target_values, dtype=float), where=desired_values != 0)
        slippage_cost = 0.0
        if slippage_fn is not None:
            for symbol in price_row.index:
                slippage_cost += slippage_fn(float(trade_notional.get(symbol, 0.0)), float(amount_row.get(symbol, 0.0)), float(vol_row.get(symbol, 0.0)))
        cash_after = portfolio_value_before - float((target_shares * price_row).sum()) - slippage_cost
        for symbol in price_row.index:
            actual_shares = float(target_shares.get(symbol, 0.0))
            target_weight = float(target_weights.get(symbol, 0.0))
            actual_value = actual_shares * float(price_row.get(symbol, 0.0))
            actual_weight = actual_value / portfolio_value_before if portfolio_value_before else 0.0
            holdings_rows.append(
                {
                    "date": date_ts.strftime("%Y-%m-%d %H:%M:%S") if date_ts.time() != pd.Timestamp(date_ts.date()).time() else date_ts.strftime("%Y-%m-%d"),
                    "symbol": symbol,
                    "target_weight": target_weight,
                    "actual_weight": actual_weight,
                    "weight_error": actual_weight - target_weight,
                    "pre_shares": float(current_prev.get(symbol, 0.0)),
                    "target_shares": float(target_shares.get(symbol, 0.0)),
                    "post_shares": actual_shares,
                    "trade_shares": float(trade_shares.get(symbol, 0.0)),
                    "fill_ratio": float(fill_ratio[price_row.index.get_loc(symbol)] if len(price_row.index) else 1.0),
                    "tradable": bool(tradable_row.get(symbol, True)),
                    "price": float(price_row.get(symbol, 0.0)),
                    "trade_notional": float(trade_notional.get(symbol, 0.0)),
                }
            )
            orders_rows.append(
                {
                    "date": date_ts.strftime("%Y-%m-%d %H:%M:%S") if date_ts.time() != pd.Timestamp(date_ts.date()).time() else date_ts.strftime("%Y-%m-%d"),
                    "symbol": symbol,
                    "trade_shares": float(trade_shares.get(symbol, 0.0)),
                    "trade_notional": float(trade_notional.get(symbol, 0.0)),
                    "target_weight": target_weight,
                    "actual_weight": actual_weight,
                    "weight_error": actual_weight - target_weight,
                    "target_shares": float(target_shares.get(symbol, 0.0)),
                    "fill_ratio": float(fill_ratio[price_row.index.get_loc(symbol)] if len(price_row.index) else 1.0),
                    "tradable": bool(tradable_row.get(symbol, True)),
                }
            )
        if i < len(dates) - 1:
            next_date = pd.Timestamp(dates[i + 1])
            next_prices = market.close.loc[next_date]
            portfolio_value_after = float(cash_after + (target_shares.reindex(next_prices.index).fillna(0.0) * next_prices).sum())
            gross_return = (portfolio_value_after - portfolio_value_before) / portfolio_value_before if portfolio_value_before else 0.0
            turnover = float(trade_shares.abs().sum())
            pnl_rows.append(
                {
                    "date": next_date.strftime("%Y-%m-%d %H:%M:%S") if next_date.time() != pd.Timestamp(next_date.date()).time() else next_date.strftime("%Y-%m-%d"),
                    "signal_date": date_ts.strftime("%Y-%m-%d %H:%M:%S") if date_ts.time() != pd.Timestamp(date_ts.date()).time() else date_ts.strftime("%Y-%m-%d"),
                    "gross_return": gross_return,
                    "turnover": turnover,
                    "slippage_cost": slippage_cost,
                    "equity_before": portfolio_value_before,
                    "equity": portfolio_value_after,
                }
            )
        prev_shares = target_shares
        cash = cash_after
    orders = pd.DataFrame(orders_rows)
    holdings = pd.DataFrame(holdings_rows)
    pnl = pd.DataFrame(pnl_rows)
    if not pnl.empty:
        pnl["cum_return"] = pnl["equity"] / float(initial_cash) - 1.0
        pnl["annualized_return"] = _annualized_return(float(pnl["cum_return"].iloc[-1]), len(pnl))
    return ExecutionRun(orders=orders, holdings=holdings, pnl=pnl)
