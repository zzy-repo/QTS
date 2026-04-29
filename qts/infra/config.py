from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from ..core.data.data_source import DEFAULT_UNIVERSE, load_market_panel
from ..core.strategy import build_strategy_spec
from ..core.strategy.specs import StrategySpec
from .models import EntryConfig, MarketConfig, QTSConfig, StrategyConfig, SystemConfig

STRATEGY_KIND_ALIASES = {
    "factor": "factor",
    "因子策略": "factor",
}

FACTOR_KIND_ALIASES = {
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

REPORT_KIND_ALIASES = {
    "backtest": "backtest",
    "回测": "backtest",
    "close": "close",
    "收盘": "close",
    "close_report": "close",
    "selection": "selection",
    "选股": "selection",
    "stock_selection": "selection",
}

DEFAULT_START_DATE = "20240102"
DEFAULT_END_DATE = "20240315"
DEFAULT_ENTRY_OUTPUTS = ["signals", "report", "run_summary"]


def _reject_unsupported_strategy_keys(raw: dict[str, object], *, index: int) -> None:
    """拒绝未支持的旧字段，避免静默误读。"""
    unsupported_keys = [key for key in ("类型", "type", "kind") if key in raw]
    if unsupported_keys:
        keys_text = ", ".join(unsupported_keys)
        raise ValueError(
            f"策略配置[{index}] 仍在使用旧字段 {keys_text}；"
            "请改用“策略类型/strategy_kind”和“因子列表/factor_kinds”"
        )


def _require_strategy_keys(raw: dict[str, object], *, index: int) -> None:
    """确保新策略配置字段完整。"""
    strategy_key_missing = "策略类型" not in raw and "strategy_kind" not in raw
    factor_key_missing = "因子列表" not in raw and "factor_kinds" not in raw
    missing: list[str] = []
    if strategy_key_missing:
        missing.append("策略类型/strategy_kind")
    if factor_key_missing:
        missing.append("因子列表/factor_kinds")
    if missing:
        missing_text = "、".join(missing)
        raise ValueError(f"策略配置[{index}] 缺少必要字段：{missing_text}")


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


def _alias_factor_kind(value: object) -> str:
    """把单个因子名称映射到内部标准名。"""
    return _alias(FACTOR_KIND_ALIASES, value, "momentum")


def _normalize_factor_kinds(value: object) -> list[str]:
    """把配置中的因子列表整理成内部统一格式。"""
    if isinstance(value, list):
        items = value
    elif value is None:
        items = []
    else:
        items = [value]
    normalized = [_alias_factor_kind(item) for item in items if str(item).strip()]
    if not normalized:
        raise ValueError("至少需要配置一个因子")
    return normalized


def _normalize_factor_weights(raw: object, factor_kinds: list[str]) -> dict[str, float]:
    """把因子权重字段整理成内部统一格式。"""
    if not isinstance(raw, dict):
        return {}
    weights: dict[str, float] = {}
    for key, value in raw.items():
        factor_kind = _alias_factor_kind(key)
        if factor_kind in factor_kinds:
            weights[factor_kind] = float(value)
    return weights


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
        _reject_unsupported_strategy_keys(raw, index=index)
        _require_strategy_keys(raw, index=index)
        factor_kinds = _normalize_factor_kinds(_pick(raw, "因子列表", "factor_kinds", default=[]))
        strategies.append(
            StrategyConfig(
                name=str(_pick(raw, "名称", "name", default=f"策略{index + 1}")),
                strategy_kind=_alias(STRATEGY_KIND_ALIASES, _pick(raw, "策略类型", "strategy_kind"), "factor"),
                factor_kinds=factor_kinds,
                factor_weights=_normalize_factor_weights(_pick(raw, "因子权重", "factor_weights", default={}), factor_kinds),
                lookback=int(_pick(raw, "回看周期", "lookback", default=20)),
                top_n=int(_pick(raw, "选取数量", "top_n", default=3)),
            )
        )
    return strategies


def _normalize_entry_outputs(value: object) -> list[str]:
    """把入口产物输出字段整理成内部统一格式。"""
    if isinstance(value, list):
        items = value
    elif value is None:
        items = list(DEFAULT_ENTRY_OUTPUTS)
    else:
        items = [value]

    aliases = {
        "signals": "signals",
        "信号": "signals",
        "signal": "signals",
        "report": "report",
        "报表": "report",
        "pnl": "pnl",
        "收益": "pnl",
        "run_summary": "run_summary",
        "summary": "run_summary",
        "run.txt": "run_summary",
        "运行摘要": "run_summary",
    }
    normalized: list[str] = []
    for item in items:
        key = str(item).strip()
        if not key:
            continue
        output = aliases.get(key, aliases.get(key.lower()))
        if output is None or output in normalized:
            continue
        normalized.append(output)
    return normalized or list(DEFAULT_ENTRY_OUTPUTS)


def _build_entry_config(payload: dict[str, object]) -> EntryConfig:
    """从原始配置中解析入口配置。"""
    entry_raw = _pick(payload, "入口", "entry", default={}) or {}
    return EntryConfig(
        name=str(_pick(entry_raw, "名称", "name", default="qts")),
        report_kind=_alias(REPORT_KIND_ALIASES, _pick(entry_raw, "报表类型", "report_kind", default="backtest"), "backtest"),
        artifact_dir=str(_pick(entry_raw, "输出目录", "artifact_dir", default="artifacts/qts")),
        outputs=_normalize_entry_outputs(_pick(entry_raw, "输出内容", "outputs", default=DEFAULT_ENTRY_OUTPUTS)),
    )


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
            StrategyConfig(name="momentum", strategy_kind="factor", factor_kinds=["momentum"], lookback=20, top_n=3),
            StrategyConfig(name="trend", strategy_kind="factor", factor_kinds=["trend"], lookback=30, top_n=3),
        ],
        entry=EntryConfig(),
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
    entry = _build_entry_config(payload)
    return QTSConfig(market=market, system=system, strategies=strategies, entry=entry)


def save_qts_config(config: QTSConfig, path: str | Path) -> Path:
    """保存系统配置。"""
    target = Path(path)
    target.write_text(json.dumps(config.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def build_strategies_from_config(config: QTSConfig) -> list[StrategySpec]:
    """按配置构建策略列表。"""
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
