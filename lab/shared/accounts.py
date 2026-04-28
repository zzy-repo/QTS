from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class AccountState:
    cash: float
    frozen_cash: float = 0.0
    positions: dict[str, float] = field(default_factory=dict)
    in_flight_orders: dict[str, dict[str, object]] = field(default_factory=dict)
    version: int = 0

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


def apply_fill(account: AccountState, symbol: str, shares: float, price: float, order_id: str) -> AccountState:
    next_state = AccountState.restore(account.snapshot())
    next_state.positions[symbol] = next_state.positions.get(symbol, 0.0) + shares
    next_state.cash -= shares * price
    next_state.in_flight_orders.pop(order_id, None)
    next_state.version += 1
    return next_state


def reserve_cash(account: AccountState, order_id: str, notional: float) -> AccountState:
    next_state = AccountState.restore(account.snapshot())
    next_state.cash -= notional
    next_state.frozen_cash += notional
    next_state.in_flight_orders[order_id] = {"notional": notional, "status": "NEW"}
    next_state.version += 1
    return next_state
