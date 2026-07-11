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
    try:
        from trade.monitor import _get_open_trades_from_db
        trades = _get_open_trades_from_db()
        if not trades:
            return
        for trade in trades:
            try:
                await _check_single_trade_db(trade)
            except Exception as e:
                log.error("Health check error for %s: %s", trade.get("coin"), e)
    except Exception as e:
        log.error("run_health_checks error: %s", e)


async def _check_single_trade_db(trade: dict):
    from trade.exchange import get_ticker_price
    from engines.coin_state import state_manager

    coin      = trade["coin"]
    open_rate = float(trade.get("entry_price") or 0)
    direction = trade.get("direction", "LONG")

    if not coin or not open_rate:
        return

    current_price = await get_ticker_price(f"{coin}USDT")
    if not current_price:
        return

    machine = state_manager.get(coin)
    context = machine.context

    d1d      = context.get("d1d", {})
    d4h      = context.get("d4h", {})
    bias     = context.get("bias", {})
    zone     = context.get("zone", {})

    retest = {
        "confirmed": machine.state == "signal_ready",
        "zone":      zone,
        "zone_type": zone.get("type", "") if zone else "",
        "score":     0,
        "status":    "confirmed" if machine.state == "signal_ready" else "pending",
    }

    sweep = {
        "detected":  bias.get("sweep_detected", False) if bias else False,
        "confirmed": bias.get("sweep_detected", False) if bias else False,
        "score":     bias.get("sweep_score",    0)     if bias else 0,
        "label":     bias.get("sweep_label",    "")    if bias else "",
    }

    oi_matrix = {
        "primary_label":   "",
        "funding_warning": "",
    }

    try:
        from data.cache import cache
        btc_data = cache.get_raw("btc_1d_data")
    except Exception:
        btc_data = None

    thesis = context.get("trigger_pattern", "")
    if context.get("entry_price"):
        thesis = (
            f"Entry at {context['entry_price']:.4f} — "
            f"{context.get('trigger_pattern', 'trigger')} in "
            f"{zone.get('type', 'zone') if zone else 'zone'}"
        )

    class _TradeMock:
        def __init__(self):
            self.direction   = direction
            self.entry_price = open_rate
            self.is_long     = direction == "LONG"

    current_state = _last_health_states.get(coin, HEALTHY)

    health = check_trade_health(
        trade           = _TradeMock(),
        current_price   = current_price,
        d1d             = d1d,
        d4h             = d4h,
        btc_data        = btc_data,
        oi_matrix       = oi_matrix,
        retest          = retest,
        sweep           = sweep,
        original_thesis = thesis,
        current_state   = current_state,
    )

    new_state = health["state"]
    _write_health_to_redis(coin, health)

    if _should_alert(coin, new_state, current_state):
        await _send_health_alert(
            coin,
            health,
            {"pair": f"{coin}/USDT:USDT", "profit_abs": 0.0}
        )
        _last_alert_times[coin] = time.time()

    _last_health_states[coin] = new_state


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
            "checked_at":     health["checked_at"],
        }
        r.setex(f"health:{coin}USDT", 120, json.dumps(payload))
    except Exception as e:
        log.error("Write health to Redis error %s: %s", coin, e)


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
        message = format_health_alert(health, coin)
        pnl     = float(trade.get("profit_abs", 0))
        pnl_str = f"+${pnl:.4f}" if pnl >= 0 else f"-${abs(pnl):.4f}"
        message += f"\nCurrent PnL: `{pnl_str}`"
        message += f"\nUse Force Sell on dashboard to close manually."
        await send(message)
        log.info("Health alert sent: %s → %s", coin, health["state"])
    except Exception as e:
        log.error("Send health alert error %s: %s", coin, e)


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
        log.error("Get health from Redis error %s: %s", coin, e)
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