from __future__ import annotations

from pathlib import Path

from omegaconf import OmegaConf

from ..core.data.data_source import DEFAULT_UNIVERSE, load_market_panel
from ..core.strategy import build_strategy_spec
from ..core.strategy.specs import StrategySpec
from .models import EntryConfig, MarketConfig, QTSConfig, StrategyConfig, SystemConfig

DEFAULT_START_DATE = "20240102"
DEFAULT_END_DATE = "20240315"
DEFAULT_ENTRY_OUTPUTS = ["signals", "report", "run_summary"]


def default_qts_config() -> QTSConfig:
    """Return the repository default runtime configuration."""
    return QTSConfig(
        market=MarketConfig(
            symbols=list(DEFAULT_UNIVERSE),
            start_date=DEFAULT_START_DATE,
            end_date=DEFAULT_END_DATE,
        ),
        system=SystemConfig(
            allocation_mode="score",
            optimizer_mode="score",
            execution_mode="backtest",
            initial_cash=1_000_000.0,
            lot_size=100,
            capital_caps={"momentum": 0.65, "trend": 0.65},
            optimizer_cap=0.4,
            max_adv_pct=0.02,
            slippage_base_bps=1.0,
            slippage_participation_scale=0.035,
            slippage_vol_scale=0.15,
        ),
        strategies=[
            StrategyConfig(name="momentum", strategy_kind="factor", factor_kinds=["momentum"], lookback=20, top_n=3),
            StrategyConfig(name="trend", strategy_kind="factor", factor_kinds=["trend"], lookback=30, top_n=3),
        ],
        entry=EntryConfig(name="qts", report_kind="backtest", artifact_dir="artifacts/qts", outputs=["signals", "pnl", "report", "run_summary"]),
    )


def load_qts_config(path: str | Path | None = None) -> QTSConfig:
    """Load a YAML config file into the strict pydantic config model."""
    if path is None:
        from .entrypoints import DEFAULT_ENTRY_CONFIG

        path = DEFAULT_ENTRY_CONFIG
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"config file does not exist: {target}")
    payload = OmegaConf.to_container(OmegaConf.load(target), resolve=True)
    return config_from_mapping(payload, source=str(target))


def config_from_mapping(payload: object, *, source: str = "<memory>") -> QTSConfig:
    """Validate a mapping payload as a QTS config."""
    if not isinstance(payload, dict):
        raise ValueError(f"config payload must define a mapping: {source}")
    normalized = dict(payload)
    normalized.pop("hydra", None)
    return QTSConfig.model_validate(normalized)


def save_qts_config(config: QTSConfig, path: str | Path) -> Path:
    """Write a config model as YAML."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    OmegaConf.save(config=OmegaConf.create(config.model_dump(mode="json")), f=str(target))
    return target


def build_strategies_from_config(config: QTSConfig) -> list[StrategySpec]:
    """Build runtime strategy specs from config."""
    return [
        build_strategy_spec(
            item.name,
            strategy_kind=item.strategy_kind,
            factor_kinds=item.factor_kinds,
            factor_weights=item.factor_weights,
            lookback=item.lookback,
            top_n=item.top_n,
        )
        for item in config.strategies
    ]


def build_system_from_config(config: QTSConfig):
    """Assemble the system facade from the config model."""
    from .system import MultiDecisionSystem

    return MultiDecisionSystem(
        strategies=build_strategies_from_config(config),
        allocation_mode=config.system.allocation_mode,
        optimizer_mode=config.system.optimizer_mode,
        execution_mode=config.system.execution_mode,
        initial_cash=config.system.initial_cash,
        lot_size=config.system.lot_size,
        capital_caps=dict(config.system.capital_caps),
        optimizer_cap=config.system.optimizer_cap,
        max_adv_pct=config.system.max_adv_pct,
        slippage_base_bps=config.system.slippage_base_bps,
        slippage_participation_scale=config.system.slippage_participation_scale,
        slippage_vol_scale=config.system.slippage_vol_scale,
    )


def load_market_from_config(config: QTSConfig, *, cache_root: Path | None = None):
    """Load the market panel for the configured date range and universe."""
    return load_market_panel(
        config.market.symbols,
        config.market.start_date,
        config.market.end_date,
        cache_root=cache_root,
        allow_synthetic_fallback=config.market.allow_synthetic_fallback,
    )


def apply_overrides(
    config: QTSConfig,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    symbols: list[str] | None = None,
    initial_cash: float | None = None,
    lot_size: int | None = None,
    allocation_mode: str | None = None,
    optimizer_mode: str | None = None,
    execution_mode: str | None = None,
    summary_only: bool | None = None,
    cache_root: str | None = None,
) -> QTSConfig:
    """Apply explicit runtime overrides and revalidate the full config."""
    payload = config.model_dump(mode="python")
    if start_date is not None:
        payload["market"]["start_date"] = start_date
    if end_date is not None:
        payload["market"]["end_date"] = end_date
    if symbols is not None:
        payload["market"]["symbols"] = list(symbols)
    if initial_cash is not None:
        payload["system"]["initial_cash"] = float(initial_cash)
    if lot_size is not None:
        payload["system"]["lot_size"] = int(lot_size)
    if allocation_mode is not None:
        payload["system"]["allocation_mode"] = allocation_mode
    if optimizer_mode is not None:
        payload["system"]["optimizer_mode"] = optimizer_mode
    if execution_mode is not None:
        payload["system"]["execution_mode"] = execution_mode
    if summary_only is not None:
        payload["runtime"]["summary_only"] = bool(summary_only)
    if cache_root is not None:
        payload["runtime"]["cache_root"] = cache_root
    return QTSConfig.model_validate(payload)
