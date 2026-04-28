from .core.data.data_source import (
    DEFAULT_SYMBOL,
    DEFAULT_UNIVERSE,
    SyncResult,
    load_market_panel,
    quality_checks,
)
from .core.data.models import AccountState, ExecutionRun, MarketPanel, PortfolioRun, StrategyInput
from .core.execution.engine import Executor
from .core.optimize.engine import Optimizer
from .core.portfolio.allocation import AllocationResult, allocate_capital
from .core.portfolio.engine import PortfolioManager
from .core.portfolio.results import StrategyRunResult, SystemRunResult, annualized_return
from .core.signal.engine import SignalGenerator
from .core.signal.specs import StrategySpec
from .core.signal.strategy import momentum_signal, trend_follow_signal, validate_strategy_output
from .infra.cli import run_cli
from .infra.config import (
    QTSConfig,
    apply_overrides,
    build_strategies_from_config,
    build_system_from_config,
    default_qts_config,
    load_market_from_config,
    load_qts_config,
    save_qts_config,
)
from .infra.entrypoints import (
    DEFAULT_BACKTEST_CONFIG,
    DEFAULT_CLOSE_REPORT_CONFIG,
    DEFAULT_STOCK_SELECTION_CONFIG,
    EntryRun,
    resolve_entry_config_path,
    run_backtest_entry,
    run_close_report_entry,
    run_stock_selection_entry,
)
from .infra.models import MarketConfig, StrategyConfig, SystemConfig
from .infra.presets import build_default_strategies, build_default_system, run_demo
from .infra.report import SIGNAL_COLUMNS, build_report, latest_signal_frame, normalize_signal_frame
from .infra.reporter import Reporter, summarize_system_run
from .infra.system import MultiDecisionSystem

__all__ = [
    "AccountState",
    "AllocationResult",
    "DEFAULT_BACKTEST_CONFIG",
    "DEFAULT_CLOSE_REPORT_CONFIG",
    "DEFAULT_STOCK_SELECTION_CONFIG",
    "DEFAULT_SYMBOL",
    "DEFAULT_UNIVERSE",
    "EntryRun",
    "ExecutionRun",
    "Executor",
    "MarketConfig",
    "MarketPanel",
    "MultiDecisionSystem",
    "Optimizer",
    "PortfolioManager",
    "PortfolioRun",
    "QTSConfig",
    "Reporter",
    "SignalGenerator",
    "StrategyConfig",
    "StrategyInput",
    "StrategyRunResult",
    "StrategySpec",
    "SystemConfig",
    "SystemRunResult",
    "SyncResult",
    "apply_overrides",
    "build_default_strategies",
    "build_default_system",
    "build_report",
    "build_strategies_from_config",
    "build_system_from_config",
    "default_qts_config",
    "load_market_panel",
    "latest_signal_frame",
    "load_market_from_config",
    "load_qts_config",
    "normalize_signal_frame",
    "resolve_entry_config_path",
    "run_backtest_entry",
    "run_cli",
    "run_close_report_entry",
    "run_demo",
    "run_stock_selection_entry",
    "save_qts_config",
    "summarize_system_run",
    "quality_checks",
    "validate_strategy_output",
    "momentum_signal",
    "trend_follow_signal",
    "annualized_return",
    "allocate_capital",
]
