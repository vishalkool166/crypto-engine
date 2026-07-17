import json
import logging
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class DecisionTrace:
    coin: str
    direction: str
    timestamp: float = field(default_factory=time.time)
    steps: list = field(default_factory=list)
    final_decision: str = "NO_TRADE"
    final_score: float = 0.0
    final_grade: str = "F"
    stopped_at: Optional[str] = None
    regime: str = ""
    session: str = ""
    score_breakdown: dict = field(default_factory=dict)

    def add_step(self, name: str, result: str, score: float = 0.0, reason: str = ""):
        self.steps.append({
            "name":   name,
            "result": result,
            "score":  score,
            "reason": reason,
        })

    def stop(self, at: str, reason: str = ""):
        self.stopped_at = at
        self.final_decision = "NO_TRADE"
        self.add_step(at, "STOPPED", 0.0, reason)

    def approve(self, grade: str, score: float):
        self.final_decision = "TRADE"
        self.final_grade = grade
        self.final_score = score

    def to_dict(self) -> dict:
        return {
            "coin":           self.coin,
            "direction":      self.direction,
            "timestamp":      self.timestamp,
            "datetime":       datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            "final_decision": self.final_decision,
            "final_score":    self.final_score,
            "final_grade":    self.final_grade,
            "stopped_at":     self.stopped_at,
            "regime":         self.regime,
            "session":        self.session,
            "score_breakdown":self.score_breakdown,
            "steps":          self.steps,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


_trace_store: dict = {}
_MAX_TRACES_PER_COIN = 10


def store_trace(trace: DecisionTrace) -> None:
    coin = trace.coin
    if coin not in _trace_store:
        _trace_store[coin] = []
    _trace_store[coin].append(trace.to_dict())
    if len(_trace_store[coin]) > _MAX_TRACES_PER_COIN:
        _trace_store[coin] = _trace_store[coin][-_MAX_TRACES_PER_COIN:]
    _write_to_redis(trace)


def get_traces(coin: str) -> list:
    return _trace_store.get(coin, [])


def get_all_traces() -> dict:
    return dict(_trace_store)


def get_latest_trace(coin: str) -> dict | None:
    traces = _trace_store.get(coin, [])
    return traces[-1] if traces else _read_from_redis(coin)


def _write_to_redis(trace: DecisionTrace) -> None:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return
        r.setex(
            f"trace:{trace.coin}",
            3600,
            trace.to_json(),
        )
        r.lpush("traces:recent", trace.to_json())
        r.ltrim("traces:recent", 0, 199)
    except Exception as e:
        log.warning("trace redis write: %s", e)


def _read_from_redis(coin: str) -> dict | None:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return None
        raw = r.get(f"trace:{coin}")
        if raw:
            return json.loads(raw)
        return None
    except Exception as e:
        log.warning("trace redis read: %s", e)
        return None


def get_recent_traces(limit: int = 50) -> list:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return []
        raw_list = r.lrange("traces:recent", 0, limit - 1)
        return [json.loads(x) for x in raw_list]
    except Exception as e:
        log.warning("get_recent_traces: %s", e)
        return []


def get_rejection_summary(traces: list) -> dict:
    summary = {}
    total = len(traces)
    for t in traces:
        stopped = t.get("stopped_at")
        if stopped:
            summary[stopped] = summary.get(stopped, 0) + 1
    result = {}
    for k, v in summary.items():
        result[k] = {
            "count": v,
            "pct":   round(v / total * 100, 1) if total > 0 else 0,
        }
    return dict(sorted(result.items(), key=lambda x: x[1]["count"], reverse=True))