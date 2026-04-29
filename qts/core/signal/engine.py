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
            signals = spec.builder(data).copy()
            if signals.empty:
                continue
            issues = validate_strategy_output(signals)
            if issues:
                issue_text = "；".join(issues)
                raise ValueError(f"策略输出不合法 strategy={spec.name}: {issue_text}")
            signals["strategy"] = spec.name
            frames.append(signals)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
