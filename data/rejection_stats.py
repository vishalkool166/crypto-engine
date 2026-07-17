import json
import logging
import time
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

REJECTION_KEYS = [
    "ema_neutral",
    "btc_context",
    "htf_alignment",
    "no_sweep",
    "sweep_score_low",
    "no_zone",
    "zone_score_low",
    "no_trigger",
    "trigger_score_low",
    "risk_sl_tight",
    "risk_sl_wide",
    "risk_rr_low",
    "risk_invalid",
    "grade_filter",
    "ml_filter",
    "session_filter",
    "combined_score_low",
    "max_open_trades",
    "daily_loss_limit",
    "loss_pause",
    "in_trade",
    "cooldown",
]

_PREFIX = "rejections"
_DAILY_PREFIX = "rejections:daily"
_TTL_LIVE = 86400 * 7
_TTL_DAILY = 86400 * 90


def _redis():
    try:
        from redis_client import get_redis
        return get_redis()
    except Exception:
        return None


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _week_key() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year}-W{now.isocalendar()[1]:02d}"


def record(reason: str, coin: str = "", direction: str = "") -> None:
    r = _redis()
    if not r:
        return
    try:
        r.hincrby(f"{_PREFIX}:total", reason, 1)
        r.expire(f"{_PREFIX}:total", _TTL_LIVE)

        today = _today_key()
        r.hincrby(f"{_DAILY_PREFIX}:{today}", reason, 1)
        r.expire(f"{_DAILY_PREFIX}:{today}", _TTL_DAILY)

        week = _week_key()
        r.hincrby(f"{_PREFIX}:weekly:{week}", reason, 1)
        r.expire(f"{_PREFIX}:weekly:{week}", _TTL_DAILY)

        if coin:
            r.hincrby(f"{_PREFIX}:coin:{coin}", reason, 1)
            r.expire(f"{_PREFIX}:coin:{coin}", _TTL_LIVE)

        r.hincrby(f"{_PREFIX}:scans", "total", 1)
        r.expire(f"{_PREFIX}:scans", _TTL_LIVE)

        if reason == "TRADE":
            r.hincrby(f"{_PREFIX}:scans", "signals", 1)

    except Exception as e:
        log.warning("rejection_stats.record: %s", e)


def record_scan(coin: str, direction: str, reason: str) -> None:
    record(reason, coin, direction)


def get_total_stats() -> dict:
    r = _redis()
    if not r:
        return {}
    try:
        raw = r.hgetall(f"{_PREFIX}:total")
        scans = r.hgetall(f"{_PREFIX}:scans")
        total_scans = int(scans.get("total", 0))
        total_signals = int(scans.get("signals", 0))
        counts = {k: int(v) for k, v in raw.items()}
        total_rejections = sum(counts.values())
        result = {}
        for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            result[k] = {
                "count": v,
                "pct":   round(v / total_scans * 100, 1) if total_scans > 0 else 0,
            }
        return {
            "total_scans":      total_scans,
            "total_signals":    total_signals,
            "total_rejections": total_rejections,
            "signal_rate":      round(total_signals / total_scans * 100, 1) if total_scans > 0 else 0,
            "by_reason":        result,
        }
    except Exception as e:
        log.warning("get_total_stats: %s", e)
        return {}


def get_daily_stats(days: int = 7) -> list:
    r = _redis()
    if not r:
        return []
    try:
        result = []
        for i in range(days):
            day = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            raw = r.hgetall(f"{_DAILY_PREFIX}:{day}")
            if not raw:
                continue
            counts = {k: int(v) for k, v in raw.items()}
            total = sum(counts.values())
            result.append({
                "date":    day,
                "total":   total,
                "by_reason": dict(sorted(counts.items(), key=lambda x: x[1], reverse=True)),
            })
        return result
    except Exception as e:
        log.warning("get_daily_stats: %s", e)
        return []


def get_weekly_stats() -> dict:
    r = _redis()
    if not r:
        return {}
    try:
        week = _week_key()
        raw = r.hgetall(f"{_PREFIX}:weekly:{week}")
        if not raw:
            return {}
        counts = {k: int(v) for k, v in raw.items()}
        total = sum(counts.values())
        result = {}
        for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            result[k] = {
                "count": v,
                "pct":   round(v / total * 100, 1) if total > 0 else 0,
            }
        return {
            "week":      week,
            "total":     total,
            "by_reason": result,
        }
    except Exception as e:
        log.warning("get_weekly_stats: %s", e)
        return {}


def get_coin_stats(coin: str) -> dict:
    r = _redis()
    if not r:
        return {}
    try:
        raw = r.hgetall(f"{_PREFIX}:coin:{coin}")
        if not raw:
            return {}
        counts = {k: int(v) for k, v in raw.items()}
        total = sum(counts.values())
        result = {}
        for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            result[k] = {
                "count": v,
                "pct":   round(v / total * 100, 1) if total > 0 else 0,
            }
        return {
            "coin":      coin,
            "total":     total,
            "by_reason": result,
        }
    except Exception as e:
        log.warning("get_coin_stats: %s", e)
        return {}


def get_top_rejections(limit: int = 5) -> list:
    stats = get_total_stats()
    by_reason = stats.get("by_reason", {})
    return [
        {"reason": k, **v}
        for k, v in list(by_reason.items())[:limit]
    ]


def reset_stats() -> None:
    r = _redis()
    if not r:
        return
    try:
        keys = r.keys(f"{_PREFIX}:*")
        if keys:
            r.delete(*keys)
        log.info("Rejection stats reset")
    except Exception as e:
        log.warning("reset_stats: %s", e)


def get_summary_line() -> str:
    stats = get_total_stats()
    if not stats:
        return "No rejection data"
    top = get_top_rejections(1)
    top_reason = top[0]["reason"] if top else "none"
    top_pct = top[0]["pct"] if top else 0
    return (
        f"Scans:{stats['total_scans']} "
        f"Signals:{stats['total_signals']} "
        f"Rate:{stats['signal_rate']}% "
        f"Top rejection:{top_reason}({top_pct}%)"
    )