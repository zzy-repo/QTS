from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..data.models import MarketPanel, StrategyInput
from .specs import StrategySpec
from .strategy import validate_strategy_output


@dataclass(frozen=True)
class SignalGenerator:
    """生成策略信号。"""

    strategies: list[StrategySpec]

    @staticmethod
    def _coerce_legacy_signal_schema(signals: pd.DataFrame) -> pd.DataFrame:
        """兼容旧版最小信号输出 schema。"""
        frame = signals.copy()
        if "score" not in frame.columns and "weight" in frame.columns:
            frame["score"] = pd.to_numeric(frame["weight"], errors="coerce")
        if "rank" not in frame.columns and "date" in frame.columns:
            ordered = frame.reset_index(drop=False).rename(columns={"index": "_legacy_order"})
            ordered["date"] = pd.to_datetime(ordered["date"], format="mixed", errors="coerce")
            ordered["rank"] = (
                ordered.groupby("date", dropna=False)["_legacy_order"]
                .rank(method="first")
                .astype("Int64")
            )
            frame["rank"] = ordered["rank"].values
        return frame

    def generate(self, market: MarketPanel) -> pd.DataFrame:
        """把市场数据转换为统一信号表。"""
        frames: list[pd.DataFrame] = []
        for spec in self.strategies:
            data = StrategyInput(
                close=market.close,
                volume=market.volume,
                amount=market.amount,
                lookback=spec.lookback,
                top_n=spec.top_n,
            )
            signals = self._coerce_legacy_signal_schema(spec.builder(data).copy())
            if signals.empty:
                continue
            issues = validate_strategy_output(signals)
            if issues:
                issue_text = "；".join(issues)
                raise ValueError(f"策略输出不合法 strategy={spec.name}: {issue_text}")
            signals["strategy"] = spec.name
            frames.append(signals)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
