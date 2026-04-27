from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal


EventType = Literal["market", "signal", "order", "fill"]


@dataclass(frozen=True)
class Event:
    type: EventType
    ts: str
    payload: dict[str, object] = field(default_factory=dict)


@dataclass
class EventBus:
    handlers: list[Callable[[Event], None]] = field(default_factory=list)
    log: list[Event] = field(default_factory=list)

    def subscribe(self, handler: Callable[[Event], None]) -> None:
        self.handlers.append(handler)

    def publish(self, event: Event) -> None:
        self.log.append(event)
        for handler in self.handlers:
            handler(event)

    def replay(self, events: list[Event]) -> None:
        for event in events:
            self.publish(event)
