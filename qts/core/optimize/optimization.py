from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class OptimizerAdapter:
    """描述一个优化器实现。"""

    name: str
    run: Callable[[pd.DataFrame], pd.DataFrame]


def _require_volatility(signals: pd.DataFrame, optimizer_name: str) -> pd.Series:
    """确保依赖波动率的优化器拿到明确可用的字段。"""
    if "volatility" not in signals.columns:
        raise ValueError(f"优化器需要 volatility 列: {optimizer_name}")
    return pd.to_numeric(signals["volatility"], errors="coerce")


def equal_weight_optimizer(signals: pd.DataFrame) -> pd.DataFrame:
    """生成等权目标权重。"""
    if signals.empty:
        return pd.DataFrame(columns=["date", "symbol", "weight", "optimizer"])
    rows: list[dict[str, object]] = []
    for date, group in signals.groupby("date"):
        symbols = list(group["symbol"])
        if not symbols:
            continue
        weight = 1.0 / len(symbols)
        for symbol in symbols:
            rows.append({"date": date, "symbol": symbol, "weight": weight, "optimizer": "equal"})
    return pd.DataFrame(rows)


def score_weight_optimizer(signals: pd.DataFrame) -> pd.DataFrame:
    """按信号得分生成目标权重。"""
    if signals.empty:
        return pd.DataFrame(columns=["date", "symbol", "weight", "optimizer"])
    rows: list[dict[str, object]] = []
    for date, group in signals.groupby("date"):
        scores = group["score"].abs().astype(float)
        total = float(scores.sum())
        if total <= 0:
            weight = 1.0 / len(group) if len(group) else 0.0
            for symbol in group["symbol"]:
                rows.append({"date": date, "symbol": symbol, "weight": weight, "optimizer": "score"})
            continue
        for _, row in group.iterrows():
            rows.append({"date": date, "symbol": row["symbol"], "weight": float(abs(row["score"]) / total), "optimizer": "score"})
    return pd.DataFrame(rows)


def inverse_vol_optimizer(signals: pd.DataFrame) -> pd.DataFrame:
    """按波动率倒数生成目标权重。"""
    if signals.empty:
        return pd.DataFrame(columns=["date", "symbol", "weight", "optimizer"])
    volatility = _require_volatility(signals, "inv_vol")
    rows: list[dict[str, object]] = []
    for date, group in signals.groupby("date"):
        vols = volatility.loc[group.index].replace(0.0, np.nan)
        inv = 1.0 / vols
        inv = inv.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        total = float(inv.sum())
        if total <= 0:
            weight = 1.0 / len(group) if len(group) else 0.0
            for symbol in group["symbol"]:
                rows.append({"date": date, "symbol": symbol, "weight": weight, "optimizer": "inv_vol"})
            continue
        for idx, row in group.iterrows():
            rows.append(
                {
                    "date": date,
                    "symbol": row["symbol"],
                    "weight": float(inv.loc[idx] / total),
                    "optimizer": "inv_vol",
                }
            )
    return pd.DataFrame(rows)


def blend_weight_optimizer(signals: pd.DataFrame, score_weight: float = 0.5) -> pd.DataFrame:
    """在得分和倒波动率之间做加权混合。"""
    if signals.empty:
        return pd.DataFrame(columns=["date", "symbol", "weight", "optimizer"])
    volatility = _require_volatility(signals, "blend")
    score_weight = float(min(max(score_weight, 0.0), 1.0))
    inv_weight = 1.0 - score_weight
    rows: list[dict[str, object]] = []
    for date, group in signals.groupby("date"):
        scores = pd.to_numeric(group["score"], errors="coerce").abs()
        score_total = float(scores.sum())
        score_component = scores / score_total if score_total > 0 else pd.Series(1.0 / len(group), index=group.index)
        vols = volatility.loc[group.index].replace(0.0, np.nan)
        inv = 1.0 / vols
        inv = inv.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        inv_total = float(inv.sum())
        inv_component = inv / inv_total if inv_total > 0 else pd.Series(1.0 / len(group), index=group.index)
        weight_series = score_weight * score_component + inv_weight * inv_component
        total = float(weight_series.sum())
        if total > 0:
            weight_series = weight_series / total
        else:
            weight_series = pd.Series(1.0 / len(group), index=group.index)
        for idx, row in group.iterrows():
            rows.append({"date": date, "symbol": row["symbol"], "weight": float(weight_series.loc[idx]), "optimizer": "blend"})
    return pd.DataFrame(rows)


def capped_optimizer(signals: pd.DataFrame, cap: float = 0.4) -> pd.DataFrame:
    """生成带权重上限的目标权重。"""
    frame = score_weight_optimizer(signals)
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["weight"] = frame["weight"].clip(lower=0.0, upper=cap)
    def _normalize(group: pd.Series) -> pd.Series:
        total = float(group.sum())
        return group / total if total > 0 else group

    frame["weight"] = frame.groupby("date")["weight"].transform(_normalize)
    frame["optimizer"] = "capped"
    return frame


def build_optimizers(capped_cap: float = 0.4) -> dict[str, OptimizerAdapter]:
    """构建可用优化器集合。"""
    def capped_run(signals: pd.DataFrame) -> pd.DataFrame:
        return capped_optimizer(signals, cap=capped_cap)

    def blend_run(signals: pd.DataFrame) -> pd.DataFrame:
        return blend_weight_optimizer(signals, score_weight=0.5)

    return {
        "equal": OptimizerAdapter(name="equal", run=equal_weight_optimizer),
        "score": OptimizerAdapter(name="score", run=score_weight_optimizer),
        "inv_vol": OptimizerAdapter(name="inv_vol", run=inverse_vol_optimizer),
        "blend": OptimizerAdapter(name="blend", run=blend_run),
        "capped": OptimizerAdapter(name="capped", run=capped_run),
    }
