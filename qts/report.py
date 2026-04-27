from __future__ import annotations

import pandas as pd

SIGNAL_COLUMNS = ["date", "symbol", "rank", "score", "weight"]


def normalize_signal_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """标准化信号字段。"""
    normalized = frame.copy()
    for column in SIGNAL_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = pd.NA
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.strftime("%Y-%m-%d")
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
    latest_date = normalized["date"].max()
    return normalized[normalized["date"].eq(latest_date)].copy().reset_index(drop=True)


def build_report(frame: pd.DataFrame, kind: str) -> pd.DataFrame:
    """生成指定类型的报表。"""
    normalized_kind = kind.strip().lower()
    if normalized_kind == "backtest":
        return _build_backtest_report(frame)
    if normalized_kind == "close":
        return _build_close_report(frame)
    if normalized_kind == "selection":
        return _build_selection_report(frame)
    raise ValueError(f"unsupported report kind: {kind}")


def _build_backtest_report(frame: pd.DataFrame) -> pd.DataFrame:
    """生成回测报表。"""
    normalized = normalize_signal_frame(frame)
    if normalized.empty:
        return pd.DataFrame(columns=["section", "date", "signal_count", "avg_score", "avg_weight", "gross_return", "equity", "cum_return"])

    daily = (
        normalized.groupby("date", as_index=False)
        .agg(
            signal_count=("symbol", "size"),
            avg_score=("score", "mean"),
            avg_weight=("weight", "mean"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    if {"gross_return", "equity", "cum_return"}.issubset(normalized.columns):
        enriched = (
            normalized.groupby("date", as_index=False)
            .agg(
                gross_return=("gross_return", "first"),
                equity=("equity", "first"),
                cum_return=("cum_return", "first"),
            )
            .sort_values("date")
            .reset_index(drop=True)
        )
        daily = daily.merge(enriched, on="date", how="left")

    summary = pd.DataFrame(
        [
            {
                "section": "summary",
                "date": None,
                "signal_count": int(len(normalized)),
                "avg_score": float(normalized["score"].mean()) if normalized["score"].notna().any() else None,
                "avg_weight": float(normalized["weight"].mean()) if normalized["weight"].notna().any() else None,
                "gross_return": float(normalized["gross_return"].dropna().iloc[-1]) if "gross_return" in normalized.columns and normalized["gross_return"].notna().any() else None,
                "equity": float(normalized["equity"].dropna().iloc[-1]) if "equity" in normalized.columns and normalized["equity"].notna().any() else None,
                "cum_return": float(normalized["cum_return"].dropna().iloc[-1]) if "cum_return" in normalized.columns and normalized["cum_return"].notna().any() else None,
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
