from __future__ import annotations

from typing import Callable, Literal

import pandas as pd

SIGNAL_COLUMNS = ["date", "symbol", "rank", "score", "weight"]
ReportKind = Literal["backtest", "close", "selection"]


def _format_signal_date(value: object) -> str:
    """保留时间粒度格式化信号时间。"""
    ts = pd.Timestamp(value)
    if ts.time() == pd.Timestamp(ts.date()).time():
        return ts.strftime("%Y-%m-%d")
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def normalize_signal_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """标准化信号字段。"""
    normalized = frame.copy()
    for column in SIGNAL_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = pd.NA
    normalized["date"] = pd.to_datetime(normalized["date"], format="mixed").map(_format_signal_date)
    normalized["symbol"] = normalized["symbol"].astype(str)
    normalized["rank"] = pd.to_numeric(normalized["rank"], errors="coerce").astype("Int64")
    normalized["score"] = pd.to_numeric(normalized["score"], errors="coerce")
    normalized["weight"] = pd.to_numeric(normalized["weight"], errors="coerce")
    ordered = SIGNAL_COLUMNS + [column for column in normalized.columns if column not in SIGNAL_COLUMNS]
    return normalized[ordered].sort_values(["date", "rank", "symbol"], kind="mergesort").reset_index(drop=True)


def latest_signal_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """提取最新交易日信号。"""
    normalized = normalize_signal_frame(frame)
    if normalized.empty:
        return normalized
    dated = pd.to_datetime(normalized["date"], format="mixed")
    latest_day = dated.dt.normalize().max()
    return normalized[dated.dt.normalize().eq(latest_day)].copy().reset_index(drop=True)


def build_report(frame: pd.DataFrame, kind: ReportKind) -> pd.DataFrame:
    """生成指定类型的报表。"""
    normalized_kind = kind.strip().lower()
    builders: dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {
        "backtest": _build_backtest_report,
        "close": _build_close_report,
        "selection": _build_selection_report,
    }
    builder = builders.get(normalized_kind)
    if builder is None:
        raise ValueError(f"不支持的报表类型：{kind}")
    return builder(frame)


def _build_backtest_report(frame: pd.DataFrame) -> pd.DataFrame:
    """生成回测报表。"""
    normalized = normalize_signal_frame(frame)
    if normalized.empty:
        return pd.DataFrame(
            columns=[
                "section",
                "date",
                "signal_date",
                "signal_count",
                "avg_score",
                "avg_weight",
                "gross_return",
                "equity",
                "cum_return",
            ]
        )

    daily = normalized.groupby("date", as_index=False).agg(
        signal_count=("symbol", "size"),
        avg_score=("score", "mean"),
        avg_weight=("weight", "mean"),
    )
    if "signal_date" in normalized.columns:
        signal_dates = normalized.groupby("date")["signal_date"].agg(
            lambda values: " | ".join(dict.fromkeys(str(value) for value in values if pd.notna(value)))
        )
        daily["signal_date"] = signal_dates.reindex(daily["date"]).to_numpy()
    else:
        daily["signal_date"] = daily["date"]
    daily = daily.sort_values("date").reset_index(drop=True)
    if {"gross_return", "equity", "cum_return"}.issubset(normalized.columns):
        metric_keys = ["date"]
        if "signal_date" in normalized.columns:
            metric_keys.append("signal_date")
        metric_source = normalized[metric_keys + ["gross_return", "equity", "cum_return"]].drop_duplicates()
        enriched = metric_source.groupby("date", as_index=False).agg(
            gross_return=("gross_return", "sum"),
            equity=("equity", "last"),
            cum_return=("cum_return", "last"),
        )
        daily = daily.merge(enriched, on="date", how="left")

    last_daily = daily.iloc[-1] if not daily.empty else None
    summary = pd.DataFrame(
        [
            {
                "section": "summary",
                "date": None,
                "signal_date": None,
                "signal_count": int(daily["signal_count"].sum()) if not daily.empty else 0,
                "avg_score": float(daily["avg_score"].mean()) if not daily.empty and daily["avg_score"].notna().any() else None,
                "avg_weight": float(daily["avg_weight"].mean()) if not daily.empty and daily["avg_weight"].notna().any() else None,
                "gross_return": float(last_daily["gross_return"]) if last_daily is not None and "gross_return" in daily.columns and pd.notna(last_daily.get("gross_return")) else None,
                "equity": float(last_daily["equity"]) if last_daily is not None and "equity" in daily.columns and pd.notna(last_daily.get("equity")) else None,
                "cum_return": float(last_daily["cum_return"]) if last_daily is not None and "cum_return" in daily.columns and pd.notna(last_daily.get("cum_return")) else None,
            }
        ]
    )
    daily.insert(0, "section", "daily")
    return pd.concat([summary, daily], ignore_index=True)


def _build_close_report(frame: pd.DataFrame) -> pd.DataFrame:
    """生成收盘决策报表。"""
    latest = latest_signal_frame(frame)
    if latest.empty:
        return pd.DataFrame(columns=["date", "symbol", "rank", "score", "weight", "decision"])
    latest = latest.copy().sort_values(["rank", "symbol"]).reset_index(drop=True)
    median_weight = float(latest["weight"].median()) if latest["weight"].notna().any() else 0.0

    decisions: list[str] = []
    for _, row in latest.iterrows():
        rank = int(row["rank"]) if pd.notna(row["rank"]) else 0
        weight = float(row["weight"]) if pd.notna(row["weight"]) else 0.0
        if rank == 1:
            decision = "买入"
        elif weight >= median_weight:
            decision = "重点关注"
        else:
            decision = "观察"
        decisions.append(decision)
    latest["decision"] = decisions
    return latest[["date", "symbol", "rank", "score", "weight", "decision"]]


def _build_selection_report(frame: pd.DataFrame) -> pd.DataFrame:
    """生成选股报表。"""
    latest = latest_signal_frame(frame)
    if latest.empty:
        return pd.DataFrame(columns=["date", "symbol", "rank", "score", "weight", "selected"])
    latest = latest.copy().sort_values(["rank", "symbol"]).reset_index(drop=True)
    latest["selected"] = True
    return latest[["date", "symbol", "rank", "score", "weight", "selected"]]
