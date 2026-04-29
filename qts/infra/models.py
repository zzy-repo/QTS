from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..core.data.models import MarketPanel
from ..core.portfolio.results import SystemRunResult

SUPPORTED_EXECUTION_MODES = {"backtest", "sim", "paper"}
SUPPORTED_REPORT_KINDS = {"backtest", "close", "selection"}
SUPPORTED_ENTRY_OUTPUTS = {"signals", "report", "pnl", "run_summary"}


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
    strategy_kind: str = "factor"
    factor_kinds: list[str]
    factor_weights: dict[str, float] = Field(default_factory=dict)
    lookback: int = 20
    top_n: int = 3

    @field_validator("name", "strategy_kind")
    @classmethod
    def _validate_non_empty_strategy_fields(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("strategy fields must be non-empty")
        return normalized

    @field_validator("strategy_kind")
    @classmethod
    def _validate_strategy_kind_supported(cls, value: str) -> str:
        from ..core.strategy import build_strategy_adapters

        if value not in build_strategy_adapters():
            raise ValueError(f"unsupported strategy_kind: {value}")
        return value

    @field_validator("factor_kinds")
    @classmethod
    def _validate_factor_kinds(cls, value: list[str]) -> list[str]:
        from ..core.factor import build_factor_adapters

        if not value:
            raise ValueError("strategies[].factor_kinds must contain at least one factor")
        adapters = build_factor_adapters()
        normalized = [item.strip() for item in value if item.strip()]
        if not normalized:
            raise ValueError("strategies[].factor_kinds must contain at least one factor")
        duplicates = sorted({item for item in normalized if normalized.count(item) > 1})
        if duplicates:
            raise ValueError(f"duplicate factor_kinds are not allowed: {duplicates}")
        unsupported = [item for item in normalized if item not in adapters]
        if unsupported:
            raise ValueError(f"unsupported factor_kinds: {unsupported}")
        return normalized

    @model_validator(mode="after")
    def _validate_factor_weights(self) -> "StrategyConfig":
        unknown = set(self.factor_weights) - set(self.factor_kinds)
        if unknown:
            raise ValueError(f"factor_weights contains unknown factors: {sorted(unknown)}")
        return self


class SystemConfig(QTSBaseModel):
    """Portfolio construction and execution configuration."""

    allocation_mode: str = "score"
    optimizer_mode: str = "score"
    execution_mode: str = "backtest"
    initial_cash: float = 1_000_000.0
    lot_size: int = 100
    capital_caps: dict[str, float] = Field(default_factory=dict)
    optimizer_cap: float = 0.4
    max_adv_pct: float = 0.02
    slippage_base_bps: float = 1.0
    slippage_participation_scale: float = 0.035
    slippage_vol_scale: float = 0.15

    @field_validator("allocation_mode", "optimizer_mode", "execution_mode")
    @classmethod
    def _validate_non_empty_mode(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("system mode fields must be non-empty")
        return normalized

    @field_validator("allocation_mode")
    @classmethod
    def _validate_allocation_mode_supported(cls, value: str) -> str:
        from ..core.portfolio.allocators import build_allocators

        if value not in build_allocators():
            raise ValueError(f"unsupported allocation_mode: {value}")
        return value

    @field_validator("optimizer_mode")
    @classmethod
    def _validate_optimizer_mode_supported(cls, value: str) -> str:
        from ..core.optimize.optimizers import build_optimizers

        if value not in build_optimizers():
            raise ValueError(f"unsupported optimizer_mode: {value}")
        return value

    @field_validator("execution_mode")
    @classmethod
    def _validate_execution_mode_supported(cls, value: str) -> str:
        if value not in SUPPORTED_EXECUTION_MODES:
            raise ValueError(f"unsupported execution_mode: {value}")
        return value


class EntryConfig(QTSBaseModel):
    """Artifact outputs for a run profile."""

    name: str = "qts"
    report_kind: str = "backtest"
    artifact_dir: str = "artifacts/qts"
    outputs: list[str] = Field(default_factory=lambda: ["signals", "report", "run_summary"])

    @field_validator("name", "report_kind")
    @classmethod
    def _validate_non_empty_entry_fields(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("entry fields must be non-empty")
        return normalized

    @field_validator("report_kind")
    @classmethod
    def _validate_report_kind_supported(cls, value: str) -> str:
        if value not in SUPPORTED_REPORT_KINDS:
            raise ValueError(f"unsupported report_kind: {value}")
        return value

    @field_validator("outputs")
    @classmethod
    def _validate_outputs_supported(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        unsupported = [item for item in normalized if item not in SUPPORTED_ENTRY_OUTPUTS]
        if unsupported:
            raise ValueError(f"unsupported entry outputs: {unsupported}")
        return normalized


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
