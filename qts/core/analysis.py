from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def _clean_series(values: pd.Series | pd.DataFrame) -> pd.Series:
    series = pd.Series(values).astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    return series


def _cumulative_drawdown(returns: pd.Series) -> pd.Series:
    equity = (1.0 + returns).cumprod()
    return equity / equity.cummax() - 1.0


def compute_tail_metrics(returns: pd.Series, alpha: float = 0.05) -> dict[str, float]:
    """计算尾部风险指标。"""
    clean = _clean_series(returns)
    if clean.empty:
        return {"cvar": np.nan, "sortino": np.nan, "mdd": np.nan, "win_rate": np.nan}
    cutoff = float(clean.quantile(alpha))
    tail = clean[clean <= cutoff]
    downside = clean[clean < 0]
    downside_std = float(downside.std(ddof=0))
    sortino = float((clean.mean() / downside_std) * np.sqrt(TRADING_DAYS_PER_YEAR)) if downside_std > 0 else np.nan
    cvar = float(tail.mean()) if not tail.empty else np.nan
    mdd = float(_cumulative_drawdown(clean).min())
    win_rate = float((clean > 0).mean())
    return {"cvar": cvar, "sortino": sortino, "mdd": mdd, "win_rate": win_rate}


def compute_performance_metrics(
    returns: pd.Series,
    benchmark: pd.Series | None = None,
    turnover: pd.Series | None = None,
) -> pd.DataFrame:
    """计算完整绩效指标。"""
    clean = _clean_series(returns)
    if clean.empty:
        return pd.DataFrame(
            [
                {
                    "annualized_return": np.nan,
                    "volatility": np.nan,
                    "sharpe": np.nan,
                    "sortino": np.nan,
                    "mdd": np.nan,
                    "beta": np.nan,
                    "alpha": np.nan,
                    "skew": np.nan,
                    "kurtosis": np.nan,
                    "turnover": np.nan,
                    "win_rate": np.nan,
                    "cvar_5": np.nan,
                }
            ]
        )

    ann_factor = np.sqrt(TRADING_DAYS_PER_YEAR)
    vol = float(clean.std(ddof=0) * ann_factor)
    sharpe_denom = float(clean.std(ddof=0))
    sharpe = float((clean.mean() / sharpe_denom) * ann_factor) if sharpe_denom else np.nan
    tail = compute_tail_metrics(clean)
    equity = (1.0 + clean).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)
    annualized = float((1.0 + total_return) ** (TRADING_DAYS_PER_YEAR / len(clean)) - 1.0) if len(clean) else np.nan
    skew = float(clean.skew())
    kurt = float(clean.kurtosis())
    beta = np.nan
    alpha = np.nan
    if benchmark is not None:
        bench = _clean_series(benchmark).reindex(clean.index).dropna()
        aligned = pd.concat([clean.reindex(bench.index), bench], axis=1).dropna()
        if not aligned.empty:
            aligned.columns = ["strategy", "benchmark"]
            bench_var = float(aligned["benchmark"].var(ddof=0))
            if bench_var > 0:
                beta = float(aligned["strategy"].cov(aligned["benchmark"]) / bench_var)
                alpha = float((aligned["strategy"].mean() - beta * aligned["benchmark"].mean()) * TRADING_DAYS_PER_YEAR)
    turnover_value = float(_clean_series(turnover).mean()) if turnover is not None else np.nan
    return pd.DataFrame(
        [
            {
                "annualized_return": annualized,
                "volatility": vol,
                "sharpe": sharpe,
                "sortino": tail["sortino"],
                "mdd": tail["mdd"],
                "beta": beta,
                "alpha": alpha,
                "skew": skew,
                "kurtosis": kurt,
                "turnover": turnover_value,
                "win_rate": tail["win_rate"],
                "cvar_5": tail["cvar"],
            }
        ]
    )


def compute_rolling_metrics(
    returns: pd.Series,
    benchmark: pd.Series | None = None,
    window: int = 20,
    label: str | None = None,
) -> pd.DataFrame:
    """计算滚动绩效指标。"""
    clean = pd.Series(returns).astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return pd.DataFrame(columns=["date", "window", "label", "rolling_sharpe", "rolling_sortino", "rolling_mdd", "rolling_win_rate"])

    bench = None
    if benchmark is not None:
        bench = pd.Series(benchmark).astype(float).replace([np.inf, -np.inf], np.nan)

    rows: list[dict[str, object]] = []
    min_periods = max(5, window // 2)
    for end in range(min_periods - 1, len(clean)):
        subset = clean.iloc[end - window + 1 : end + 1].dropna()
        if subset.empty:
            continue
        tail = compute_tail_metrics(subset)
        row: dict[str, object] = {
            "date": clean.index[end],
            "window": window,
            "label": label or f"window_{window}",
            "rolling_sharpe": float(subset.mean() / subset.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR)) if subset.std(ddof=0) else np.nan,
            "rolling_sortino": tail["sortino"],
            "rolling_mdd": tail["mdd"],
            "rolling_win_rate": tail["win_rate"],
        }
        if bench is not None:
            aligned = pd.concat([subset, bench.reindex(subset.index)], axis=1).dropna()
            if not aligned.empty:
                aligned.columns = ["strategy", "benchmark"]
                bench_var = float(aligned["benchmark"].var(ddof=0))
                row["rolling_beta"] = float(aligned["strategy"].cov(aligned["benchmark"]) / bench_var) if bench_var > 0 else np.nan
            else:
                row["rolling_beta"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def risk_state_machine(
    equity: pd.Series,
    window: int = 20,
    drawdown_warn: float = -0.03,
    drawdown_halt: float = -0.08,
    vol_warn: float = 0.18,
    vol_halt: float = 0.30,
) -> pd.DataFrame:
    """根据权益曲线生成风险状态。"""
    clean = pd.Series(equity).astype(float).dropna()
    if clean.empty:
        return pd.DataFrame(columns=["equity", "rolling_return", "rolling_vol", "drawdown", "state"])
    returns = clean.pct_change().fillna(0.0)
    rolling_vol = returns.rolling(window, min_periods=max(3, window // 2)).std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR)
    rolling_return = returns.rolling(window, min_periods=max(3, window // 2)).mean() * TRADING_DAYS_PER_YEAR
    drawdown = clean / clean.cummax() - 1.0
    states: list[str] = []
    for dd, vol in zip(drawdown, rolling_vol.fillna(0.0)):
        if dd <= drawdown_halt or vol >= vol_halt:
            states.append("halt")
        elif dd <= drawdown_warn or vol >= vol_warn:
            states.append("caution")
        else:
            states.append("normal")
    return pd.DataFrame(
        {
            "equity": clean,
            "rolling_return": rolling_return,
            "rolling_vol": rolling_vol,
            "drawdown": drawdown,
            "state": states,
        }
    )


def historical_completeness(frame: pd.DataFrame, *, date_column: str = "date", symbol_column: str = "symbol") -> pd.DataFrame:
    """统计历史覆盖率。"""
    if frame.empty or date_column not in frame.columns:
        return pd.DataFrame(columns=[symbol_column, "expected_days", "actual_days", "missing_days", "completeness"])
    rows: list[dict[str, object]] = []
    dates = pd.to_datetime(frame[date_column])
    start = dates.min()
    end = dates.max()
    expected = pd.bdate_range(start, end)
    expected_count = len(expected)
    if symbol_column in frame.columns:
        groups = frame.groupby(symbol_column)
    else:
        groups = [("all", frame)]
    for symbol, group in groups:
        group_dates = pd.to_datetime(group[date_column]).drop_duplicates().sort_values()
        missing = len(expected.difference(group_dates))
        rows.append(
            {
                symbol_column: symbol,
                "expected_days": expected_count,
                "actual_days": len(group_dates),
                "missing_days": missing,
                "completeness": len(group_dates) / expected_count if expected_count else np.nan,
            }
        )
    return pd.DataFrame(rows)


def selection_stability(selection: pd.DataFrame) -> pd.DataFrame:
    """计算连续日期的选股稳定性。"""
    if selection.empty or "date" not in selection.columns or "symbol" not in selection.columns:
        return pd.DataFrame(columns=["date", "selected_count", "overlap_rate", "turnover_rate"])
    rows: list[dict[str, object]] = []
    for date, group in selection.groupby("date"):
        rows.append({"date": date, "selected": set(group["symbol"])})
    rows = sorted(rows, key=lambda item: item["date"])
    result: list[dict[str, object]] = []
    previous: set[str] | None = None
    for item in rows:
        current = item["selected"]
        if previous is None:
            overlap = np.nan
            turnover = np.nan
        else:
            union = previous | current
            overlap = len(previous & current) / len(union) if union else np.nan
            turnover = 1.0 - overlap if np.isfinite(overlap) else np.nan
        result.append(
            {
                "date": item["date"],
                "selected_count": len(current),
                "overlap_rate": overlap,
                "turnover_rate": turnover,
            }
        )
        previous = current
    return pd.DataFrame(result)


def equal_weight_benchmark(close: pd.DataFrame) -> pd.Series:
    """构建等权基准收益序列。"""
    if close.empty:
        return pd.Series(dtype=float)
    return close.pct_change().mean(axis=1).fillna(0.0)


def performance_summary_from_pnl(
    pnl: pd.DataFrame,
    *,
    benchmark: pd.Series | None = None,
    return_column: str = "gross_return",
    turnover_column: str = "turnover",
) -> pd.DataFrame:
    """把 PnL 表直接汇总为绩效指标。"""
    if pnl.empty or return_column not in pnl.columns:
        return compute_performance_metrics(pd.Series(dtype=float), benchmark=benchmark)
    returns = pd.Series(pd.to_numeric(pnl[return_column], errors="coerce").values, index=pd.to_datetime(pnl["date"]))
    turnover = (
        pd.Series(pd.to_numeric(pnl[turnover_column], errors="coerce").values, index=pd.to_datetime(pnl["date"]))
        if turnover_column in pnl.columns
        else None
    )
    benchmark_series = benchmark.reindex(returns.index) if benchmark is not None else None
    return compute_performance_metrics(returns, benchmark=benchmark_series, turnover=turnover)


def cap_proxy_benchmark(close: pd.DataFrame, volume: pd.DataFrame) -> pd.Series:
    """构建市值代理基准收益序列。"""
    if close.empty or volume.empty:
        return pd.Series(dtype=float)
    cap_proxy = (close * volume).replace([np.inf, -np.inf], np.nan)
    weights = cap_proxy.div(cap_proxy.sum(axis=1), axis=0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    returns = close.pct_change().fillna(0.0)
    return (weights * returns).sum(axis=1).fillna(0.0)
