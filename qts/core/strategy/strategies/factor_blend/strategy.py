from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from ....data.models import StrategyInput
from ....factor import get_factor_adapter


def _strategy_input(data: StrategyInput, *, lookback: int, top_n: int) -> StrategyInput:
    """基于策略参数重建输入对象。"""
    return StrategyInput(
        close=data.close,
        volume=data.volume,
        amount=data.amount,
        lookback=lookback,
        top_n=top_n,
    )


def _zscore(values: pd.Series) -> pd.Series:
    series = pd.to_numeric(values, errors="coerce").astype(float)
    std = float(series.std(ddof=0))
    if not np.isfinite(std) or std <= 0.0:
        return pd.Series(0.0, index=series.index, dtype=float)
    mean = float(series.mean())
    return (series - mean) / std


def _normalize_factor_weights(
    factor_kinds: list[str],
    factor_weights: dict[str, float],
) -> pd.Series:
    weights = pd.Series(factor_weights, dtype=float).reindex(factor_kinds).fillna(0.0)
    total = float(weights.abs().sum())
    if total <= 0.0:
        weights.loc[:] = 1.0
        total = float(weights.abs().sum())
    return weights / total


def _normalize_factor_frame(frame: pd.DataFrame, factor_kind: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["date", "symbol"])
    required = {"date", "symbol", "score"}
    if not required.issubset(frame.columns):
        missing = ", ".join(sorted(required - set(frame.columns)))
        raise ValueError(f"因子输出缺少字段 factor={factor_kind}: {missing}")

    normalized = frame.copy()
    metadata_columns = [column for column in normalized.columns if column not in {"date", "symbol", "score", "rank"}]
    rename_map = {column: f"{column}_{factor_kind}" for column in metadata_columns}
    normalized = normalized.rename(columns=rename_map)
    normalized[f"score_{factor_kind}"] = normalized.groupby("date", group_keys=False)["score"].transform(_zscore)
    normalized[f"selected_{factor_kind}"] = 1.0
    return normalized.drop(columns=["score"])


def _coalesce_metadata(merged: pd.DataFrame, factor_kinds: list[str]) -> tuple[pd.DataFrame, list[str]]:
    metadata_names: set[str] = set()
    for column in merged.columns:
        for factor_kind in factor_kinds:
            suffix = f"_{factor_kind}"
            if column.endswith(suffix) and not column.startswith("score_") and not column.startswith("selected_"):
                metadata_names.add(column[: -len(suffix)])
                break

    output_columns: list[str] = []
    for metadata_name in sorted(metadata_names):
        source_columns = [
            f"{metadata_name}_{factor_kind}"
            for factor_kind in factor_kinds
            if f"{metadata_name}_{factor_kind}" in merged.columns
        ]
        if not source_columns:
            continue
        value = merged[source_columns[0]]
        for source_column in source_columns[1:]:
            value = value.combine_first(merged[source_column])
        merged[metadata_name] = value
        output_columns.append(metadata_name)
    return merged, output_columns


def _blend_weights(selected: pd.DataFrame) -> pd.Series:
    shifted = selected["score"] - float(selected["score"].min())
    positive = shifted.clip(lower=0.0)
    total = float(positive.sum())
    if total <= 0.0:
        return pd.Series(1.0 / len(selected), index=selected.index, dtype=float)
    return positive / total


def build_factor_strategy(
    factor_kinds: list[str],
    factor_weights: dict[str, float],
    lookback: int,
    top_n: int,
) -> Callable[[StrategyInput], pd.DataFrame]:
    """把一个或多个因子实现包装成可执行策略。"""
    if not factor_kinds:
        raise ValueError("至少需要提供一个因子")
    normalized_weights = _normalize_factor_weights(factor_kinds, factor_weights)

    def builder(data: StrategyInput) -> pd.DataFrame:
        merged: pd.DataFrame | None = None
        strategy_data = _strategy_input(data, lookback=lookback, top_n=top_n)
        for factor_kind in factor_kinds:
            factor_frame = get_factor_adapter(factor_kind).run(strategy_data).copy()
            normalized_frame = _normalize_factor_frame(factor_frame, factor_kind)
            if normalized_frame.empty:
                continue
            if merged is None:
                merged = normalized_frame
            else:
                merged = merged.merge(normalized_frame, on=["date", "symbol"], how="outer")

        if merged is None or merged.empty:
            return pd.DataFrame(columns=["date", "symbol", "rank", "score", "weight"])

        score_columns = [f"score_{factor_kind}" for factor_kind in factor_kinds if f"score_{factor_kind}" in merged.columns]
        selected_columns = [f"selected_{factor_kind}" for factor_kind in factor_kinds if f"selected_{factor_kind}" in merged.columns]
        merged[score_columns] = merged[score_columns].fillna(0.0)
        merged[selected_columns] = merged[selected_columns].fillna(0.0)
        merged["factor_hits"] = merged[selected_columns].sum(axis=1)
        merged["score"] = 0.0
        for factor_kind in factor_kinds:
            score_column = f"score_{factor_kind}"
            if score_column in merged.columns:
                merged["score"] = merged["score"] + merged[score_column] * float(normalized_weights[factor_kind])

        merged, metadata_columns = _coalesce_metadata(merged, factor_kinds)
        rows: list[dict[str, object]] = []
        for date, group in merged.groupby("date", sort=True):
            ranked = group.sort_values(["score", "factor_hits", "symbol"], ascending=[False, False, True]).head(top_n).copy()
            if ranked.empty:
                continue
            weights = _blend_weights(ranked)
            for rank, (_, row) in enumerate(ranked.iterrows(), start=1):
                payload = {
                    "date": date,
                    "symbol": row["symbol"],
                    "rank": rank,
                    "score": float(row["score"]),
                    "weight": float(weights.loc[row.name]),
                    "factor_hits": int(row["factor_hits"]),
                }
                for column in metadata_columns:
                    payload[column] = row.get(column)
                rows.append(payload)
        return pd.DataFrame(rows)

    return builder
