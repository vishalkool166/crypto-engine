import logging
import time
from datetime import datetime, timezone

from engines.health import (
    check_trade_health, format_health_alert,
    HEALTHY, WARNING, INVALIDATED
)

log = logging.getLogger(__name__)

_last_health_states: dict = {}
_last_alert_times:   dict = {}
_ALERT_COOLDOWN = 300


async def run_health_checks():
    """
    Runs health checks on all active Freqtrade trades.
    Called every 1 minute by scheduler.
    Writes health state to Redis.
    Sends Telegram alert on state change.
    """
    try:
        from api.freqtrade import _ft_get
        trades = await _ft_get("/status")

        if not trades or not isinstance(trades, list) or len(trades) == 0:
            return

        for trade in trades:
            try:
                await _check_single_trade(trade)
            except Exception as e:
                pair = trade.get("pair", "--")
                log.error(f"Health check error for {pair}: {e}")

    except Exception as e:
        log.error(f"run_health_checks error: {e}")


async def _check_single_trade(trade: dict):
    pair      = trade.get("pair", "")
    coin      = pair.replace("/USDT:USDT", "").replace("/USDT", "")
    trade_id  = trade.get("trade_id", 0)
    open_rate = float(trade.get("open_rate", 0))
    is_short  = trade.get("is_short", False)
    direction = "SHORT" if is_short else "LONG"

    if not coin or not open_rate:
        return

    current_price = _get_current_price(coin)
    if not current_price:
        log.debug(f"No current price for {coin} — skipping health check")
        return

    cached = _get_cached_signal(coin)
    if not cached:
        log.debug(f"No cached signal for {coin} — skipping health check")
        return

    d1d      = cached.get("d1d", {})
    d4h      = cached.get("d4h", {})
    retest   = cached.get("retest", {})
    sweep    = cached.get("sweep", {})
    oi_matrix = cached.get("oi_matrix", {})
    expl     = cached.get("explanation", {})
    thesis   = expl.get("thesis", "")

    btc_data = _get_btc_data()

    class _TradeMock:
        def __init__(self):
            self.direction   = direction
            self.entry_price = open_rate
            self.is_long     = not is_short

    trade_obj = _TradeMock()

    current_state = _last_health_states.get(coin, HEALTHY)

    health = check_trade_health(
        trade          = trade_obj,
        current_price  = current_price,
        d1d            = d1d,
        d4h            = d4h,
        btc_data       = btc_data,
        oi_matrix      = oi_matrix,
        retest         = retest,
        sweep          = sweep,
        original_thesis = thesis,
        current_state  = current_state
    )

    new_state = health["state"]

    _write_health_to_redis(coin, health)

    if _should_alert(coin, new_state, current_state):
        await _send_health_alert(coin, health, trade)
        _last_alert_times[coin] = time.time()

    _last_health_states[coin] = new_state

    log.debug(
        f"Health check: {coin} {direction} "
        f"state:{new_state} "
        f"move:{health['move_pct']:+.2f}% "
        f"failures:{len(health['failures'])} "
        f"warnings:{len(health['warnings'])}"
    )


def _get_current_price(coin: str) -> float | None:
    try:
        from redis_client import get_redis
        import json
        r = get_redis()
        if not r:
            return None
        data = r.get(f"ticker:{coin}USDT")
        if data:
            return float(json.loads(data).get("last", 0))
        from data.cache import cache
        cached = cache.get_raw(f"signal_{coin}")
        if cached:
            return float(cached.get("market", {}).get("price", 0))
        return None
    except Exception as e:
        log.error(f"Get current price error {coin}: {e}")
        return None


def _get_cached_signal(coin: str) -> dict | None:
    try:
        from data.cache import cache
        return cache.get_raw(f"signal_{coin}")
    except Exception:
        return None


def _get_btc_data() -> dict | None:
    try:
        from data.cache import cache
        return cache.get_raw("btc_1d_data")
    except Exception:
        return None


def _write_health_to_redis(coin: str, health: dict):
    try:
        from redis_client import get_redis
        import json
        r = get_redis()
        if not r:
            return

        payload = {
            "state":          health["state"],
            "failures":       health["failures"],
            "warnings":       health["warnings"],
            "checks":         health["checks"],
            "move_pct":       health["move_pct"],
            "adverse_atr":    health["adverse_atr"],
            "is_healthy":     health["is_healthy"],
            "is_warning":     health["is_warning"],
            "is_invalidated": health["is_invalidated"],
            "checked_at":     health["checked_at"]
        }

        r.setex(f"health:{coin}USDT", 120, json.dumps(payload))

    except Exception as e:
        log.error(f"Write health to Redis error {coin}: {e}")


def _should_alert(coin: str, new_state: str, current_state: str) -> bool:
    if new_state == current_state:
        return False

    last_alert = _last_alert_times.get(coin, 0)
    if time.time() - last_alert < _ALERT_COOLDOWN:
        return False

    return True


async def _send_health_alert(coin: str, health: dict, trade: dict):
    try:
        from alerts.telegram import send
        from engines.health import format_health_alert

        message = format_health_alert(health, coin)

        pnl     = float(trade.get("profit_abs", 0))
        pnl_str = f"+${pnl:.4f}" if pnl >= 0 else f"-${abs(pnl):.4f}"

        message += f"\nCurrent PnL: `{pnl_str}`"
        message += f"\nUse Force Sell on dashboard to close manually."

        await send(message)
        log.info(f"Health alert sent: {coin} → {health['state']}")

    except Exception as e:
        log.error(f"Send health alert error {coin}: {e}")


def get_health_from_redis(coin: str) -> dict | None:
    try:
        from redis_client import get_redis
        import json
        r = get_redis()
        if not r:
            return None
        data = r.get(f"health:{coin}USDT")
        if not data:
            return None
        return json.loads(data)
    except Exception as e:
        log.error(f"Get health from Redis error {coin}: {e}")
        return None


def clear_health_state(coin: str):
    _last_health_states.pop(coin, None)
    _last_alert_times.pop(coin, None)
    try:
        from redis_client import get_redis
        r = get_redis()
        if r:
            r.delete(f"health:{coin}USDT")
    except Exception:
        pass