from __future__ import annotations

import pandas as pd

from entry_helpers import latest_signal_frame, normalize_signal_frame


def _build_backtest_report(frame: pd.DataFrame) -> pd.DataFrame:
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
    latest = latest_signal_frame(frame)
    if latest.empty:
        return pd.DataFrame(columns=["date", "symbol", "rank", "score", "weight", "selected"])
    latest = latest.copy().sort_values(["rank", "symbol"]).reset_index(drop=True)
    latest["selected"] = True
    return latest[["date", "symbol", "rank", "score", "weight", "selected"]]


def build_report(frame: pd.DataFrame, kind: str) -> pd.DataFrame:
    normalized_kind = kind.strip().lower()
    if normalized_kind == "backtest":
        return _build_backtest_report(frame)
    if normalized_kind == "close":
        return _build_close_report(frame)
    if normalized_kind == "selection":
        return _build_selection_report(frame)
    raise ValueError(f"unsupported report kind: {kind}")

