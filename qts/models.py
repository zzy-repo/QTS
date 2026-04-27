from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class StrategyInput:
    close: pd.DataFrame
    volume: pd.DataFrame | None = None
    amount: pd.DataFrame | None = None
    lookback: int = 20
    top_n: int = 3


@dataclass(frozen=True)
class MarketPanel:
    close: pd.DataFrame
    volume: pd.DataFrame
    amount: pd.DataFrame
    source_mode: str


@dataclass(frozen=True)
class ExecutionRun:
    orders: pd.DataFrame
    holdings: pd.DataFrame
    pnl: pd.DataFrame


@dataclass(frozen=True)
class PortfolioRun:
    holdings: pd.DataFrame
    pnl: pd.DataFrame
    equity: pd.DataFrame


@dataclass
class AccountState:
    cash: float
    frozen_cash: float = 0.0
    positions: dict[str, float] | None = None
    in_flight_orders: dict[str, dict[str, object]] | None = None
    version: int = 0

    def __post_init__(self) -> None:
        if self.positions is None:
            self.positions = {}
        if self.in_flight_orders is None:
            self.in_flight_orders = {}

    def equity(self, prices: pd.Series) -> float:
        value = self.cash + self.frozen_cash
        for symbol, shares in self.positions.items():
            value += float(shares) * float(prices.get(symbol, 0.0))
        return float(value)

    def snapshot(self) -> dict[str, object]:
        return {
            "cash": self.cash,
            "frozen_cash": self.frozen_cash,
            "positions": dict(self.positions),
            "in_flight_orders": {key: dict(value) for key, value in self.in_flight_orders.items()},
            "version": self.version,
        }

    @classmethod
    def restore(cls, payload: dict[str, object]) -> "AccountState":
        return cls(
            cash=float(payload["cash"]),
            frozen_cash=float(payload.get("frozen_cash", 0.0)),
            positions={str(k): float(v) for k, v in payload.get("positions", {}).items()},
            in_flight_orders={str(k): dict(v) for k, v in payload.get("in_flight_orders", {}).items()},
            version=int(payload.get("version", 0)),
        )
