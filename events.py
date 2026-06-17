import asyncio
from typing import Callable

_handlers: list[Callable] = []

def on_event(handler: Callable):
    if handler not in _handlers:
        _handlers.append(handler)

async def emit(event_type: str, data: dict = None):
    for handler in _handlers:
        try:
            await handler(event_type, data)
        except Exception:
            pass