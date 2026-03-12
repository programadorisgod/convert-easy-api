"""Simple in-memory event bus for domain events.

Implements the Observer pattern to decouple event producers from consumers.
Domain events allow different parts of the system to react to state changes
without tight coupling.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


logger = logging.getLogger(__name__)


class DomainEvent(BaseModel):
    """Base class for all domain events."""

    model_config = ConfigDict(frozen=True)  # Events are immutable

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    aggregate_id: str
    data: dict[str, Any] = Field(default_factory=dict)


EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventBus:
    """In-memory event bus for domain events."""

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._global_handlers: list[EventHandler] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe a handler to a specific event type.

        Args:
            event_type: Type of event to listen for
            handler: Async function to call when event occurs
        """
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe a handler to all events.

        Args:
            handler: Async function to call for any event
        """
        self._global_handlers.append(handler)

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all subscribed handlers.

        Args:
            event: Domain event to publish
        """

        # Call type-specific handlers
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    f"Error in event handler for {event.event_type}: {e}", exc_info=True
                )

        # Call global handlers
        for handler in self._global_handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Error in global event handler: {e}", exc_info=True)

    def clear(self) -> None:
        """Clear all event handlers (useful for testing)."""
        self._handlers.clear()
        self._global_handlers.clear()


# Global singleton event bus
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
