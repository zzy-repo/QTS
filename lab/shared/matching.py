from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd


OrderStatus = Literal["NEW", "PARTIAL", "FILLED", "CANCEL"]


@dataclass(frozen=True)
class OrderEvent:
    order_id: str
    symbol: str
    shares: float
    price: float
    status: OrderStatus
    ts: str


def simulate_match(
    order_id: str,
    symbol: str,
    shares: float,
    price: float,
    available_volume: float,
    ts: str,
) -> list[OrderEvent]:
    events: list[OrderEvent] = [OrderEvent(order_id, symbol, shares, price, "NEW", ts)]
    if available_volume <= 0:
        events.append(OrderEvent(order_id, symbol, 0.0, price, "CANCEL", ts))
        return events
    fillable = min(abs(shares), available_volume)
    if fillable < abs(shares):
        events.append(OrderEvent(order_id, symbol, float(fillable), price, "PARTIAL", ts))
        return events
    events.append(OrderEvent(order_id, symbol, float(shares), price, "FILLED", ts))
    return events
