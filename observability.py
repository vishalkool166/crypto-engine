"""Low-cardinality request correlation and in-process HTTP diagnostics."""
from __future__ import annotations

from collections import defaultdict
from contextvars import ContextVar
import re
import threading
import time
import uuid

request_id_var: ContextVar[str] = ContextVar('request_id', default='system')
_SAFE_ID = re.compile(r'^[A-Za-z0-9._-]{1,64}$')


class RequestMetrics:
    """Bounded counters keyed only by registered route templates, method and status class."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[tuple[str, str, str], int] = defaultdict(int)
        self._duration_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._duration_max: dict[tuple[str, str], float] = defaultdict(float)

    def record(self, method: str, route: str, status: int, elapsed: float) -> None:
        key = (method, route, f'{status // 100}xx')
        route_key = (method, route)
        with self._lock:
            self._counts[key] += 1
            self._duration_sum[route_key] += elapsed
            self._duration_max[route_key] = max(self._duration_max[route_key], elapsed)

    def snapshot(self) -> dict:
        with self._lock:
            counts = [
                {'method': method, 'route': route, 'status_class': status, 'count': count}
                for (method, route, status), count in sorted(self._counts.items())
            ]
            latency = [
                {
                    'method': method,
                    'route': route,
                    'count': sum(n for (m, r, _), n in self._counts.items() if (m, r) == (method, route)),
                    'mean_ms': round(total * 1000 / max(1, sum(n for (m, r, _), n in self._counts.items() if (m, r) == (method, route))), 2),
                    'max_ms': round(self._duration_max[(method, route)] * 1000, 2),
                }
                for method, route in sorted(self._duration_sum)
                for total in (self._duration_sum[(method, route)],)
            ]
        return {'scope': 'this_process_since_start', 'requests': counts, 'latency': latency}


request_metrics = RequestMetrics()


def request_id(candidate: str | None) -> str:
    if candidate and _SAFE_ID.fullmatch(candidate):
        return candidate
    return uuid.uuid4().hex


def route_template(request) -> str:
    route = request.scope.get('route')
    path = getattr(route, 'path', None)
    return path if isinstance(path, str) else 'unmatched'
