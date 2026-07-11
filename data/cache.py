import time
import json
import logging
from typing import Any

log = logging.getLogger(__name__)


class Cache:
    def __init__(self):
        self._store: dict = {}

    def set(self, key: str, value: Any, ttl: int = 1800):
        self._store[key] = {
            "value":   value,
            "expires": time.time() + ttl,
            "price":   self._extract_price(value)
        }
        try:
            from redis_client import get_redis
            r = get_redis()
            if r:
                r.setex(f"cache:{key}", ttl, json.dumps(value, default=str))
        except Exception:
            pass

    def get(self, key: str, current_price: float = None) -> Any:
        item = self._store.get(key)
        if item:
            if time.time() > item["expires"]:
                del self._store[key]
            else:
                if current_price and item.get("price"):
                    move = abs(current_price - item["price"]) / item["price"]
                    if move > 0.005:
                        del self._store[key]
                        return None
                return item["value"]

        value = self._redis_get(key)
        return value

    def get_raw(self, key: str) -> Any:
        item = self._store.get(key)
        if item:
            if time.time() > item["expires"]:
                del self._store[key]
            else:
                return item["value"]

        return self._redis_get(key)

    def _redis_get(self, key: str) -> Any:
        try:
            from redis_client import get_redis
            r = get_redis()
            if not r:
                return None
            raw = r.get(f"cache:{key}")
            if not raw:
                return None
            value = json.loads(raw)
            self._store[key] = {
                "value":   value,
                "expires": time.time() + 1800,
                "price":   self._extract_price(value)
            }
            return value
        except Exception:
            return None

    def clear(self, key: str):
        self._store.pop(key, None)
        try:
            from redis_client import get_redis
            r = get_redis()
            if r:
                r.delete(f"cache:{key}")
        except Exception:
            pass

    def clear_all(self):
        self._store.clear()
        try:
            from redis_client import get_redis
            r = get_redis()
            if r:
                keys = r.keys("cache:*")
                if keys:
                    r.delete(*keys)
        except Exception:
            pass

    def _extract_price(self, value: Any) -> float:
        if isinstance(value, dict):
            market = value.get("market", {})
            if market.get("price"):
                return float(market["price"])
            if value.get("price"):
                return float(value["price"])
        return None


cache = Cache()