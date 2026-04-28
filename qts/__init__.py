from .core.data.data_source import (
    DEFAULT_SYMBOL,
    DEFAULT_UNIVERSE,
    SyncResult,
    fetch_daily_history,
    load_market_panel,
    normalize_daily_history,
    quality_checks,
    save_csv,
    sync_symbol_history,
)
from .core.data.models import AccountState, ExecutionRun, MarketPanel, PortfolioRun, StrategyInput
from .core.execution.engine import Executor
from .core.execution.execution import dynamic_slippage_cost, execute_rebalance
from .core.optimize.engine import Optimizer
from .core.optimize.optimization import (
    OptimizerAdapter,
    build_optimizers,
    capped_optimizer,
    equal_weight_optimizer,
    score_weight_optimizer,
)
from .core.portfolio.allocation import AllocationResult, allocate_capital
from .core.portfolio.engine import PortfolioManager
from .core.portfolio.resilience import (
    ExecutionAdapter,
    build_execution_adapters,
    build_strategy_fleet,
    expand_to_ticks,
    fingerprint_frame,
)
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
    "ExecutionAdapter",
    "ExecutionRun",
    "Executor",
    "MarketConfig",
    "MarketPanel",
    "MultiDecisionSystem",
    "Optimizer",
    "OptimizerAdapter",
    "PortfolioManager",
    "PortfolioRun",
    "QTSConfig",
    "Reporter",
    "SIGNAL_COLUMNS",
    "SignalGenerator",
    "StrategyConfig",
    "StrategyInput",
    "StrategyRunResult",
    "StrategySpec",
    "SystemConfig",
    "SystemRunResult",
    "SyncResult",
    "allocate_capital",
    "annualized_return",
    "apply_overrides",
    "build_default_strategies",
    "build_default_system",
    "build_execution_adapters",
    "build_report",
    "build_optimizers",
    "build_strategy_fleet",
    "build_strategies_from_config",
    "build_system_from_config",
    "capped_optimizer",
    "default_qts_config",
    "dynamic_slippage_cost",
    "equal_weight_optimizer",
    "execute_rebalance",
    "expand_to_ticks",
    "fetch_daily_history",
    "fingerprint_frame",
    "latest_signal_frame",
    "load_market_from_config",
    "load_market_panel",
    "load_qts_config",
    "momentum_signal",
    "normalize_daily_history",
    "normalize_signal_frame",
    "quality_checks",
    "resolve_entry_config_path",
    "run_backtest_entry",
    "run_cli",
    "run_close_report_entry",
    "run_demo",
    "run_stock_selection_entry",
    "save_csv",
    "save_qts_config",
    "score_weight_optimizer",
    "summarize_system_run",
    "sync_symbol_history",
    "trend_follow_signal",
    "validate_strategy_output",
]
