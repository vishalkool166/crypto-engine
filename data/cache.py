import time
from typing import Any


class Cache:
    def __init__(self):
        self._store: dict = {}

    def set(self, key: str, value: Any, ttl: int = 300):
        self._store[key] = {
            "value":   value,
            "expires": time.time() + ttl
        }

    def get(self, key: str) -> Any:
        item = self._store.get(key)
        if not item:
            return None
        if time.time() > item["expires"]:
            del self._store[key]
            return None
        return item["value"]

    def clear(self, key: str):
        self._store.pop(key, None)

    def clear_all(self):
        self._store.clear()


cache = Cache()