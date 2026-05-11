from __future__ import annotations

from collections import defaultdict
from typing import Any, Awaitable, Callable


class EventBus:
    """Async pub/sub event bus. Schedule callbacks on the running event loop."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[Any], Awaitable[None]]]] = defaultdict(list)

    def subscribe(self, event: str, callback: Callable[[Any], Awaitable[None]]) -> None:
        self._subscribers[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable[[Any], Awaitable[None]]) -> None:
        try:
            self._subscribers[event].remove(callback)
        except (ValueError, KeyError):
            pass

    async def _safe_call(
        self,
        event: str,
        cb: Callable[[Any], Awaitable[None]],
        data: Any,
        on_error: Callable[[str, Exception], None] | None = None,
    ) -> None:
        try:
            await cb(data)
        except Exception as exc:
            if on_error:
                on_error(event, exc)

    def emit(self, event: str, data: Any = None, on_error: Callable[[str, Exception], None] | None = None) -> None:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for cb in self._subscribers.get(event, []):
            loop.create_task(self._safe_call(event, cb, data, on_error))
