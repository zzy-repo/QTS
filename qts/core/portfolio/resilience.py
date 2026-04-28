from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Callable

import pandas as pd

from ..data.models import ExecutionRun, MarketPanel
from ..execution.execution import dynamic_slippage_cost, execute_rebalance


@dataclass(frozen=True)
class ExecutionAdapter:
    """描述一个执行适配器。"""

    name: str
    run: Callable[..., ExecutionRun]


def fingerprint_frame(frame: pd.DataFrame) -> str:
    """计算数据帧指纹。"""
    return sha256(frame.to_csv(index=True).encode("utf-8")).hexdigest()


def build_execution_adapters(
    *,
    slippage_base_bps: float = 1.0,
    participation_scale: float = 0.035,
    vol_scale: float = 0.15,
    max_adv_pct: float = 0.02,
) -> dict[str, ExecutionAdapter]:
    """构建可用执行适配器。"""
    def slippage(trade_notional: float, adv_notional: float, volatility: float) -> float:
        return dynamic_slippage_cost(
            trade_notional,
            adv_notional,
            volatility,
            base_bps=slippage_base_bps,
            participation_scale=participation_scale,
            vol_scale=vol_scale,
        )

    def run_backtest(target: pd.DataFrame, market: MarketPanel, *, initial_cash: float = 1_000_000.0, lot_size: int = 100, **_: object) -> ExecutionRun:
        return execute_rebalance(
            target,
            market,
            initial_cash=initial_cash,
            lot_size=lot_size,
        )

    def run_sim(target: pd.DataFrame, market: MarketPanel, *, initial_cash: float = 1_000_000.0, lot_size: int = 100, **_: object) -> ExecutionRun:
        return execute_rebalance(
            target,
            market,
            initial_cash=initial_cash,
            lot_size=lot_size,
            slippage_fn=slippage,
        )

    def run_paper(target: pd.DataFrame, market: MarketPanel, *, initial_cash: float = 1_000_000.0, lot_size: int = 100, **_: object) -> ExecutionRun:
        return execute_rebalance(
            target,
            market,
            initial_cash=initial_cash,
            lot_size=lot_size,
            max_adv_pct=max_adv_pct,
            slippage_fn=slippage,
        )

    return {
        "backtest": ExecutionAdapter(name="backtest", run=run_backtest),
        "sim": ExecutionAdapter(name="sim", run=run_sim),
        "paper": ExecutionAdapter(name="paper", run=run_paper),
    }


def expand_to_ticks(close: pd.DataFrame, bars_per_day: int = 3) -> pd.DataFrame:
    """把日线展开成更细粒度的模拟时点。"""
    rows: list[pd.DataFrame] = []
    for ts, row in close.iterrows():
        for bar in range(bars_per_day):
            tick_ts = pd.Timestamp(ts) + pd.Timedelta(minutes=bar * 5)
            tick_row = row.copy()
            tick_row.name = tick_ts
            rows.append(tick_row.to_frame().T)
    expanded = pd.concat(rows, axis=0)
    expanded.index = pd.to_datetime(expanded.index)
    return expanded.sort_index()


def build_strategy_fleet(builder: Callable[[int], pd.DataFrame], count: int) -> pd.DataFrame:
    """批量生成策略信号集合。"""
    frames: list[pd.DataFrame] = []
    for idx in range(count):
        frame = builder(idx).copy()
        frame["strategy"] = f"s{idx:03d}"
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
