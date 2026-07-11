import logging
from engines.indicators import calculate_all
from config import cfg

log = logging.getLogger(__name__)

SE = cfg.SCALP_ENGINE


def get_direction(d4h: dict) -> str:
    price = d4h.get("price", 0)
    ema20 = d4h.get("ema20")
    atr   = d4h.get("atr")

    if not price or not ema20 or not atr:
        return "NEUTRAL"

    buffer = atr * SE["ema_buffer_atr_mult"]

    if price > ema20 + buffer:
        return "LONG"
    if price < ema20 - buffer:
        return "SHORT"
    return "NEUTRAL"


def get_btc_filter(direction: str) -> bool:
    try:
        from data.cache import cache
        from trade.ws import get_mark_price

        btc = cache.get_raw("btc_4h_data")
        if not btc:
            return True

        btc_cls = btc.get("trend", {}).get("cls", "neutral")
        btc_adx = btc.get("adx") or 0

        if btc_adx < 28:
            return True

        if direction == "LONG" and btc_cls == "bear":
            return False
        if direction == "SHORT" and btc_cls == "bull":
            return False

        return True

    except Exception as e:
        log.warning("get_btc_filter: %s", e)
        return True


def check(d4h: dict, coin: str) -> dict:
    direction = get_direction(d4h)

    if direction == "NEUTRAL":
        return {"pass": False, "direction": "NEUTRAL", "reason": "price_near_ema"}

    if coin != "BTC":
        btc_ok = get_btc_filter(direction)
        if not btc_ok:
            return {"pass": False, "direction": direction, "reason": "btc_conflict"}

    return {"pass": True, "direction": direction, "reason": ""}