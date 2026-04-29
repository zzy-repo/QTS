from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..core.data.models import MarketPanel
from ..core.portfolio.results import SystemRunResult

StrategyKind = Literal["factor"]
FactorKind = Literal["momentum", "trend", "sharpe"]
AllocationMode = Literal["score", "equal", "risk_parity", "optimized"]
OptimizerMode = Literal["score", "equal", "inv_vol", "blend", "capped"]
ExecutionMode = Literal["backtest", "sim", "paper"]
ReportKind = Literal["backtest", "close", "selection"]
EntryOutput = Literal["signals", "report", "pnl", "run_summary"]


class QTSBaseModel(BaseModel):
    """Shared pydantic settings for config models."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RuntimeConfig(QTSBaseModel):
    """Runtime-only options consumed by the CLI entrypoint."""

    summary_only: bool = False
    cache_root: str | None = None


class MarketConfig(QTSBaseModel):
    """Market data range and universe."""

    symbols: list[str]
    start_date: str
    end_date: str
    allow_synthetic_fallback: bool = False

    @field_validator("symbols")
    @classmethod
    def _validate_symbols(cls, value: list[str]) -> list[str]:
        symbols = [item.strip() for item in value if item.strip()]
        if not symbols:
            raise ValueError("market.symbols must contain at least one symbol")
        return symbols


class StrategyConfig(QTSBaseModel):
    """Single strategy configuration."""

    name: str
    strategy_kind: StrategyKind = "factor"
    factor_kinds: list[FactorKind]
    factor_weights: dict[str, float] = Field(default_factory=dict)
    lookback: int = 20
    top_n: int = 3

    @field_validator("factor_kinds")
    @classmethod
    def _validate_factor_kinds(cls, value: list[FactorKind]) -> list[FactorKind]:
        if not value:
            raise ValueError("strategies[].factor_kinds must contain at least one factor")
        return value

    @model_validator(mode="after")
    def _validate_factor_weights(self) -> "StrategyConfig":
        unknown = set(self.factor_weights) - set(self.factor_kinds)
        if unknown:
            raise ValueError(f"factor_weights contains unknown factors: {sorted(unknown)}")
        return self


class SystemConfig(QTSBaseModel):
    """Portfolio construction and execution configuration."""

    allocation_mode: AllocationMode = "score"
    optimizer_mode: OptimizerMode = "score"
    execution_mode: ExecutionMode = "backtest"
    initial_cash: float = 1_000_000.0
    lot_size: int = 100
    capital_caps: dict[str, float] = Field(default_factory=dict)
    optimizer_cap: float = 0.4
    max_adv_pct: float = 0.02
    slippage_base_bps: float = 1.0
    slippage_participation_scale: float = 0.035
    slippage_vol_scale: float = 0.15


class EntryConfig(QTSBaseModel):
    """Artifact outputs for a run profile."""

    name: str = "qts"
    report_kind: ReportKind = "backtest"
    artifact_dir: str = "artifacts/qts"
    outputs: list[EntryOutput] = Field(default_factory=lambda: ["signals", "report", "run_summary"])


class QTSConfig(QTSBaseModel):
    """Root configuration for a full system run."""

    market: MarketConfig
    system: SystemConfig
    strategies: list[StrategyConfig]
    entry: EntryConfig = Field(default_factory=EntryConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)

    @field_validator("strategies")
    @classmethod
    def _validate_strategies(cls, value: list[StrategyConfig]) -> list[StrategyConfig]:
        if not value:
            raise ValueError("strategies must contain at least one strategy")
        return value


@dataclass(frozen=True)
class EntryRun:
    """Persisted outputs from a single entry run."""

    name: str
    config_path: Path | None
    artifact_dir: Path
    outputs: list[str]
    config: QTSConfig
    market: MarketPanel
    result: SystemRunResult
    signals: pd.DataFrame
    report: pd.DataFrame
