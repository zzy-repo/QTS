from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..data.models import ExecutionRun, MarketPanel
from ..portfolio.resilience import build_execution_adapters


@dataclass(frozen=True)
class Executor:
    """把目标权重执行成成交结果。"""

    mode: str = "backtest"
    slippage_base_bps: float = 1.0
    participation_scale: float = 0.035
    vol_scale: float = 0.15
    max_adv_pct: float = 0.02

    def execute(
        self,
        target: pd.DataFrame,
        market: MarketPanel,
        *,
        initial_cash: float = 1_000_000.0,
        lot_size: int = 100,
    ) -> ExecutionRun:
        """执行目标组合。"""
        adapter = build_execution_adapters(
            slippage_base_bps=self.slippage_base_bps,
            participation_scale=self.participation_scale,
            vol_scale=self.vol_scale,
            max_adv_pct=self.max_adv_pct,
        ).get(self.mode)
        if adapter is None:
            raise ValueError(f"未知的执行模式：{self.mode}")
        return adapter.run(target, market, initial_cash=initial_cash, lot_size=lot_size)
