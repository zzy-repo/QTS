from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from ..core.data.data_source import DEFAULT_UNIVERSE, load_market_panel
from ..core.signal import build_strategy_spec
from ..core.signal.specs import StrategySpec
from .models import MarketConfig, QTSConfig, StrategyConfig, SystemConfig

STRATEGY_KIND_ALIASES = {
    "momentum": "momentum",
    "动量": "momentum",
    "trend": "trend",
    "趋势": "trend",
    "sharpe": "sharpe",
    "夏普": "sharpe",
}

ALLOCATION_MODE_ALIASES = {
    "score": "score",
    "打分": "score",
    "equal": "equal",
    "等权": "equal",
    "risk_parity": "risk_parity",
    "风险平价": "risk_parity",
    "optimized": "optimized",
    "优化组合": "optimized",
}

OPTIMIZER_MODE_ALIASES = {
    "score": "score",
    "打分": "score",
    "equal": "equal",
    "等权": "equal",
    "inv_vol": "inv_vol",
    "逆波动率": "inv_vol",
    "blend": "blend",
    "混合": "blend",
    "capped": "capped",
    "截断": "capped",
}

EXECUTION_MODE_ALIASES = {
    "backtest": "backtest",
    "回测": "backtest",
    "sim": "sim",
    "模拟": "sim",
    "paper": "paper",
    "纸面": "paper",
}

DEFAULT_START_DATE = "20240102"
DEFAULT_END_DATE = "20240315"


def _pick(mapping: dict[str, object], *keys: str, default: object = None) -> object:
    """从候选键中取配置值。"""
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _alias(mapping: dict[str, str], value: object, default: str) -> str:
    """把配置值映射到内部标准名。"""
    text = str(value)
    return mapping.get(text, mapping.get(text.lower(), default))


def _as_bool(value: object, default: bool = False) -> bool:
    """把配置值归一为布尔值。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on", "是", "启用", "开启"}:
        return True
    if text in {"0", "false", "no", "n", "off", "否", "禁用", "关闭"}:
        return False
    return default


def _build_market_config(payload: dict[str, object]) -> MarketConfig:
    """从原始配置中解析市场配置。"""
    market_raw = _pick(payload, "市场", "market", default={}) or {}
    return MarketConfig(
        symbols=list(_pick(market_raw, "标的池", "symbols", default=DEFAULT_UNIVERSE)),
        start_date=str(_pick(market_raw, "开始日期", "start_date", default=DEFAULT_START_DATE)),
        end_date=str(_pick(market_raw, "结束日期", "end_date", default=DEFAULT_END_DATE)),
        allow_synthetic_fallback=_as_bool(_pick(market_raw, "允许合成回退", "allow_synthetic_fallback", default=False)),
    )


def _normalize_capital_caps(raw: object) -> dict[str, float]:
    """把资本上限字段整理成内部统一格式。"""
    if not isinstance(raw, dict):
        return {}
    payload = raw
    return {str(k): float(v) for k, v in payload.items()}


def _build_system_config(payload: dict[str, object]) -> SystemConfig:
    """从原始配置中解析系统配置。"""
    system_raw = _pick(payload, "系统", "system", default={}) or {}
    return SystemConfig(
        allocation_mode=_alias(ALLOCATION_MODE_ALIASES, _pick(system_raw, "分配器", "allocation_mode", default="score"), "score"),
        optimizer_mode=_alias(OPTIMIZER_MODE_ALIASES, _pick(system_raw, "优化器", "optimizer_mode", default="score"), "score"),
        execution_mode=_alias(EXECUTION_MODE_ALIASES, _pick(system_raw, "执行器", "execution_mode", default="backtest"), "backtest"),
        initial_cash=float(_pick(system_raw, "初始资金", "initial_cash", default=1_000_000.0)),
        lot_size=int(_pick(system_raw, "手数", "lot_size", default=100)),
        capital_caps=_normalize_capital_caps(_pick(system_raw, "资本上限", "capital_caps", default={})),
        optimizer_cap=float(_pick(system_raw, "优化器截断上限", "optimizer_cap", default=0.4)),
        max_adv_pct=float(_pick(system_raw, "最大ADV占比", "max_adv_pct", default=0.02)),
        slippage_base_bps=float(_pick(system_raw, "基础滑点bp", "slippage_base_bps", default=1.0)),
        slippage_participation_scale=float(_pick(system_raw, "参与率滑点系数", "slippage_participation_scale", default=0.035)),
        slippage_vol_scale=float(_pick(system_raw, "波动率滑点系数", "slippage_vol_scale", default=0.15)),
    )


def _build_strategy_configs(payload: dict[str, object]) -> list[StrategyConfig]:
    """从原始配置中解析策略列表。"""
    strategies_raw = _pick(payload, "策略", "strategies", default=[]) or []
    strategies: list[StrategyConfig] = []
    for index, raw in enumerate(strategies_raw):
        if not isinstance(raw, dict):
            continue
        strategies.append(
            StrategyConfig(
                name=str(_pick(raw, "名称", "name", default=f"策略{index + 1}")),
                kind=_alias(STRATEGY_KIND_ALIASES, _pick(raw, "类型", "type", default="momentum"), "momentum"),
                lookback=int(_pick(raw, "回看周期", "lookback", default=20)),
                top_n=int(_pick(raw, "选取数量", "top_n", default=3)),
            )
        )
    return strategies


def default_qts_config() -> QTSConfig:
    """生成默认系统配置。"""
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
            StrategyConfig(name="momentum", kind="momentum", lookback=20, top_n=3),
            StrategyConfig(name="trend", kind="trend", lookback=30, top_n=3),
        ],
    )


def load_qts_config(path: str | Path | None = None) -> QTSConfig:
    """加载系统配置。"""
    if path is None:
        repo_root = Path(__file__).resolve().parents[2]
        candidates = [
            repo_root / "configs" / "qts.config.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                path = candidate
                break
        else:
            return default_qts_config()

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    market = _build_market_config(payload)
    system = _build_system_config(payload)
    strategies = _build_strategy_configs(payload) or list(default_qts_config().strategies)
    return QTSConfig(market=market, system=system, strategies=strategies)


def save_qts_config(config: QTSConfig, path: str | Path) -> Path:
    """保存系统配置。"""
    target = Path(path)
    target.write_text(json.dumps(config.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def build_strategies_from_config(config: QTSConfig) -> list[StrategySpec]:
    """按配置构建策略列表。"""
    return [
        build_strategy_spec(item.name, item.kind, lookback=item.lookback, top_n=item.top_n)
        for item in config.strategies
    ]


def build_system_from_config(config: QTSConfig):
    """按配置构建系统门面。"""
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
    """按配置加载市场面板。"""
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
) -> QTSConfig:
    """用命令行参数覆盖配置。"""
    market = config.market
    system = config.system
    if start_date is not None:
        market = replace(market, start_date=start_date)
    if end_date is not None:
        market = replace(market, end_date=end_date)
    if symbols is not None:
        market = replace(market, symbols=list(symbols))
    if initial_cash is not None:
        system = replace(system, initial_cash=float(initial_cash))
    if lot_size is not None:
        system = replace(system, lot_size=int(lot_size))
    if allocation_mode is not None:
        system = replace(system, allocation_mode=_alias(ALLOCATION_MODE_ALIASES, allocation_mode, system.allocation_mode))
    if optimizer_mode is not None:
        system = replace(system, optimizer_mode=_alias(OPTIMIZER_MODE_ALIASES, optimizer_mode, system.optimizer_mode))
    if execution_mode is not None:
        system = replace(system, execution_mode=_alias(EXECUTION_MODE_ALIASES, execution_mode, system.execution_mode))
    return replace(config, market=market, system=system)
