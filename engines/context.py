import logging
from engines.indicators import calculate_all
from config import cfg

log = logging.getLogger(__name__)

SE = cfg.SCALP_ENGINE


def get_direction(d4h: dict) -> str:
    price = d4h.get("price", 0)
    ema20 = d4h.get("ema20")
    ema50 = d4h.get("ema50")
    atr   = d4h.get("atr")

    if not price or not ema20 or not ema50 or not atr:
        return "NEUTRAL"

    buffer = atr * SE["ema_buffer_atr_mult"]

    if price > ema20 + buffer and ema20 > ema50:
        return "LONG"
    if price < ema20 - buffer and ema20 < ema50:
        return "SHORT"
    return "NEUTRAL"


def get_higher_tf_bias(df, tf: str) -> str:
    if df is None or len(df) < 20:
        return "NEUTRAL"
    try:
        d    = calculate_all(df, timeframe=tf)
        price = d.get("price", 0)
        ema20 = d.get("ema20")
        ema50 = d.get("ema50")
        atr   = d.get("atr")

        if not price or not ema20 or not ema50 or not atr:
            return "NEUTRAL"

        buffer = atr * SE["ema_buffer_atr_mult"]

        if price > ema20 + buffer and ema20 > ema50:
            return "LONG"
        if price < ema20 - buffer and ema20 < ema50:
            return "SHORT"
        return "NEUTRAL"
    except Exception as e:
        log.warning("get_higher_tf_bias %s: %s", tf, e)
        return "NEUTRAL"


def check_higher_tf_alignment(
    direction:    str,
    daily_bias:   str,
    weekly_bias:  str,
) -> dict:
    opposite = "SHORT" if direction == "LONG" else "LONG"

    if daily_bias == opposite:
        return {
            "pass":      False,
            "reason":    "daily_opposing",
            "daily":     daily_bias,
            "weekly":    weekly_bias,
            "size_mult": 0.0,
            "alignment": "blocked",
        }

    if weekly_bias == opposite:
        return {
            "pass":      False,
            "reason":    "weekly_opposing",
            "daily":     daily_bias,
            "weekly":    weekly_bias,
            "size_mult": 0.0,
            "alignment": "blocked",
        }

    both_confirm    = daily_bias == direction and weekly_bias == direction
    one_confirms    = daily_bias == direction or  weekly_bias == direction
    both_neutral    = daily_bias == "NEUTRAL"  and weekly_bias == "NEUTRAL"

    if both_confirm:
        size_mult = 1.3
        alignment = "strong"
    elif one_confirms:
        size_mult = 1.0
        alignment = "normal"
    else:
        size_mult = 0.7
        alignment = "weak"

    return {
        "pass":      True,
        "reason":    "",
        "daily":     daily_bias,
        "weekly":    weekly_bias,
        "size_mult": size_mult,
        "alignment": alignment,
    }


def get_btc_filter(direction: str) -> bool:
    try:
        from data.cache import cache
        btc = cache.get_raw("btc_4h_data")
        if not btc:
            return True

        btc_cls = btc.get("trend", {}).get("cls", "neutral")
        btc_adx = float(btc.get("adx") or 0)

        if btc_adx >= 28:
            if direction == "LONG"  and btc_cls == "bear":
                return False
            if direction == "SHORT" and btc_cls == "bull":
                return False
        return True

    except Exception as e:
        log.warning("get_btc_filter: %s", e)
        return True


def check(
    d4h:      dict,
    coin:     str,
    df_1d=    None,
    df_1w=    None,
) -> dict:
    direction = get_direction(d4h)

    if direction == "NEUTRAL":
        return {
            "pass":      False,
            "direction": "NEUTRAL",
            "reason":    "price_near_ema",
            "alignment": None,
        }

    if coin != "BTC":
        btc_ok = get_btc_filter(direction)
        if not btc_ok:
            return {
                "pass":      False,
                "direction": direction,
                "reason":    "btc_conflict",
                "alignment": None,
            }

    daily_bias  = get_higher_tf_bias(df_1d, "1d") if df_1d is not None else "NEUTRAL"
    weekly_bias = get_higher_tf_bias(df_1w, "1w") if df_1w is not None else "NEUTRAL"

    alignment = check_higher_tf_alignment(direction, daily_bias, weekly_bias)

    if not alignment["pass"]:
        return {
            "pass":      False,
            "direction": direction,
            "reason":    alignment["reason"],
            "alignment": alignment,
        }

    return {
        "pass":      True,
        "direction": direction,
        "reason":    "",
        "alignment": alignment,
    }