from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ..core.data.models import MarketPanel
from ..core.portfolio.results import SystemRunResult


@dataclass(frozen=True)
class MarketConfig:
    """描述市场数据配置。"""

    symbols: list[str]
    start_date: str
    end_date: str
    allow_synthetic_fallback: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "标的池": list(self.symbols),
            "开始日期": self.start_date,
            "结束日期": self.end_date,
            "允许合成回退": self.allow_synthetic_fallback,
        }


@dataclass(frozen=True)
class StrategyConfig:
    """描述单个策略配置。"""

    name: str
    kind: str
    lookback: int = 20
    top_n: int = 3

    def to_dict(self) -> dict[str, object]:
        return {
            "名称": self.name,
            "类型": {"momentum": "动量", "trend": "趋势"}.get(self.kind, self.kind),
            "回看周期": self.lookback,
            "选取数量": self.top_n,
        }


@dataclass(frozen=True)
class SystemConfig:
    """描述系统运行配置。"""

    allocation_mode: str = "score"
    optimizer_mode: str = "score"
    execution_mode: str = "backtest"
    initial_cash: float = 1_000_000.0
    lot_size: int = 100
    capital_caps: dict[str, float] = field(default_factory=dict)
    optimizer_cap: float = 0.4
    max_adv_pct: float = 0.02
    slippage_base_bps: float = 1.0
    slippage_participation_scale: float = 0.035
    slippage_vol_scale: float = 0.15

    def to_dict(self) -> dict[str, object]:
        return {
            "分配器": {"score": "打分", "equal": "等权", "risk_parity": "风险平价", "optimized": "优化组合"}.get(self.allocation_mode, self.allocation_mode),
            "优化器": {"score": "打分", "equal": "等权", "inv_vol": "逆波动率", "blend": "混合", "capped": "截断"}.get(self.optimizer_mode, self.optimizer_mode),
            "执行器": {"backtest": "回测", "sim": "模拟", "paper": "纸面"}.get(self.execution_mode, self.execution_mode),
            "初始资金": self.initial_cash,
            "手数": self.lot_size,
            "资本上限": dict(self.capital_caps),
            "优化器截断上限": self.optimizer_cap,
            "最大ADV占比": self.max_adv_pct,
            "基础滑点bp": self.slippage_base_bps,
            "参与率滑点系数": self.slippage_participation_scale,
            "波动率滑点系数": self.slippage_vol_scale,
        }


@dataclass(frozen=True)
class QTSConfig:
    """描述完整系统配置。"""

    market: MarketConfig
    system: SystemConfig
    strategies: list[StrategyConfig]

    def to_dict(self) -> dict[str, object]:
        return {
            "市场": self.market.to_dict(),
            "系统": self.system.to_dict(),
            "策略": [strategy.to_dict() for strategy in self.strategies],
        }


@dataclass(frozen=True)
class EntryRun:
    """保存单入口运行结果。"""

    name: str
    config_path: Path | None
    config: QTSConfig
    market: MarketPanel
    result: SystemRunResult
    signals: pd.DataFrame
    report: pd.DataFrame
