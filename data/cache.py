import time
from typing import Any


class Cache:
    def __init__(self):
        self._store: dict = {}

    def set(self, key: str, value: Any, ttl: int = 300):
        self._store[key] = {
            "value":   value,
            "expires": time.time() + ttl,
            "price":   self._extract_price(value)
        }

    def get(self, key: str, current_price: float = None) -> Any:
        item = self._store.get(key)
        if not item:
            return None
        if time.time() > item["expires"]:
            del self._store[key]
            return None
        if current_price and item.get("price"):
            cached_price = item["price"]
            move = abs(current_price - cached_price) / cached_price
            if move > 0.005:
                del self._store[key]
                return None
        return item["value"]

    def get_raw(self, key: str) -> Any:
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

    def _extract_price(self, value: Any) -> float:
        if isinstance(value, dict):
            market = value.get("market", {})
            if market.get("price"):
                return float(market["price"])
            if value.get("price"):
                return float(value["price"])
        return None


cache = Cache()