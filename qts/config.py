from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .data_source import DEFAULT_UNIVERSE, load_market_panel
from .engine import StrategySpec
from .models import StrategyInput
from .strategy import momentum_signal, trend_follow_signal

STRATEGY_KIND_ALIASES = {
    "momentum": "momentum",
    "动量": "momentum",
    "trend": "trend",
    "趋势": "trend",
}

OPTIMIZER_MODE_ALIASES = {
    "score": "score",
    "打分": "score",
    "equal": "equal",
    "等权": "equal",
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


def _pick(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _alias(mapping: dict[str, str], value: Any, default: str) -> str:
    text = str(value)
    return mapping.get(text, mapping.get(text.lower(), default))


@dataclass(frozen=True)
class MarketConfig:
    symbols: list[str]
    start_date: str
    end_date: str

    def to_dict(self) -> dict[str, object]:
        return {
            "标的池": list(self.symbols),
            "开始日期": self.start_date,
            "结束日期": self.end_date,
        }


@dataclass(frozen=True)
class StrategyConfig:
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
            "优化器": {"score": "打分", "equal": "等权", "capped": "截断"}.get(self.optimizer_mode, self.optimizer_mode),
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
    market: MarketConfig
    system: SystemConfig
    strategies: list[StrategyConfig]

    def to_dict(self) -> dict[str, object]:
        return {
            "市场": self.market.to_dict(),
            "系统": self.system.to_dict(),
            "策略": [strategy.to_dict() for strategy in self.strategies],
        }


def default_qts_config() -> QTSConfig:
    return QTSConfig(
        market=MarketConfig(
            symbols=list(DEFAULT_UNIVERSE),
            start_date="20240102",
            end_date="20240315",
        ),
        system=SystemConfig(
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
    if path is None:
        repo_root = Path(__file__).resolve().parents[1]
        candidates = [
            repo_root / "configs" / "qts.config.json",
            repo_root / "qts.config.json",
            Path("qts.config.json"),
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
    market_raw = _pick(payload, "市场", "market", default={}) or {}
    system_raw = _pick(payload, "系统", "system", default={}) or {}
    strategies_raw = _pick(payload, "策略", "strategies", default=[]) or []

    market = MarketConfig(
        symbols=list(_pick(market_raw, "标的池", "symbols", default=DEFAULT_UNIVERSE)),
        start_date=str(_pick(market_raw, "开始日期", "start_date", default="20240102")),
        end_date=str(_pick(market_raw, "结束日期", "end_date", default="20240315")),
    )
    system = SystemConfig(
        optimizer_mode=_alias(OPTIMIZER_MODE_ALIASES, _pick(system_raw, "优化器", "optimizer_mode", default="score"), "score"),
        execution_mode=_alias(EXECUTION_MODE_ALIASES, _pick(system_raw, "执行器", "execution_mode", default="backtest"), "backtest"),
        initial_cash=float(_pick(system_raw, "初始资金", "initial_cash", default=1_000_000.0)),
        lot_size=int(_pick(system_raw, "手数", "lot_size", default=100)),
        capital_caps={str(k): float(v) for k, v in (_pick(system_raw, "资本上限", "capital_caps", default={}) or {}).items()},
        optimizer_cap=float(_pick(system_raw, "优化器截断上限", "optimizer_cap", default=0.4)),
        max_adv_pct=float(_pick(system_raw, "最大ADV占比", "max_adv_pct", default=0.02)),
        slippage_base_bps=float(_pick(system_raw, "基础滑点bp", "slippage_base_bps", default=1.0)),
        slippage_participation_scale=float(_pick(system_raw, "参与率滑点系数", "slippage_participation_scale", default=0.035)),
        slippage_vol_scale=float(_pick(system_raw, "波动率滑点系数", "slippage_vol_scale", default=0.15)),
    )

    strategies: list[StrategyConfig] = []
    for index, raw in enumerate(strategies_raw or []):
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

    if not strategies:
        strategies = list(default_qts_config().strategies)
    return QTSConfig(market=market, system=system, strategies=strategies)


def save_qts_config(config: QTSConfig, path: str | Path) -> Path:
    target = Path(path)
    target.write_text(json.dumps(config.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def build_strategies_from_config(config: QTSConfig):
    strategies = []
    for item in config.strategies:
        if item.kind == "momentum":
            builder = lambda data, lookback=item.lookback, top_n=item.top_n: momentum_signal(
                StrategyInput(close=data.close, volume=data.volume, amount=data.amount, lookback=lookback, top_n=top_n)
            )
        elif item.kind == "trend":
            builder = lambda data, lookback=item.lookback, top_n=item.top_n: trend_follow_signal(
                StrategyInput(close=data.close, volume=data.volume, amount=data.amount, lookback=lookback, top_n=top_n)
            )
        else:
            raise ValueError(f"不支持的策略类型: {item.kind}")

        strategies.append(StrategySpec(name=item.name, builder=builder, lookback=item.lookback, top_n=item.top_n))
    return strategies


def build_system_from_config(config: QTSConfig):
    from .engine import MultiDecisionSystem

    return MultiDecisionSystem(
        strategies=build_strategies_from_config(config),
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
    return load_market_panel(
        config.market.symbols,
        config.market.start_date,
        config.market.end_date,
        cache_root=cache_root,
    )


def apply_overrides(
    config: QTSConfig,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    symbols: list[str] | None = None,
    initial_cash: float | None = None,
    lot_size: int | None = None,
    optimizer_mode: str | None = None,
    execution_mode: str | None = None,
) -> QTSConfig:
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
    if optimizer_mode is not None:
        system = replace(system, optimizer_mode=optimizer_mode)
    if execution_mode is not None:
        system = replace(system, execution_mode=execution_mode)
    return replace(config, market=market, system=system)
