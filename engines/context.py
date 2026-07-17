import logging
from engines.indicators import calculate_all
from engines.scorer import score_btc_context, score_htf_alignment, SignalScore
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
        d     = calculate_all(df, timeframe=tf)
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


def get_btc_context() -> dict:
    try:
        from data.cache import cache
        btc = cache.get_raw("btc_4h_data")
        if not btc:
            return {"cls": "neutral", "adx": 0.0, "available": False}
        return {
            "cls":       btc.get("trend", {}).get("cls", "neutral"),
            "adx":       float(btc.get("adx") or 0),
            "available": True,
        }
    except Exception as e:
        log.warning("get_btc_context: %s", e)
        return {"cls": "neutral", "adx": 0.0, "available": False}


def check(
    d4h:   dict,
    coin:  str,
    df_1d=None,
    df_1w=None,
) -> dict:
    from data.rejection_stats import record_scan

    direction = get_direction(d4h)

    if direction == "NEUTRAL":
        record_scan(coin, "NEUTRAL", "ema_neutral")
        return {
            "pass":         False,
            "direction":    "NEUTRAL",
            "reason":       "ema_neutral",
            "btc_score":    0.0,
            "htf_score":    0.0,
            "context_score":0.0,
            "alignment":    None,
            "trace":        {
                "ema":  "NEUTRAL — price between EMAs",
                "btc":  "skipped",
                "htf":  "skipped",
            },
        }

    btc = get_btc_context()
    btc_score, btc_reason = score_btc_context(
        btc["cls"], btc["adx"], direction
    )

    daily_bias  = get_higher_tf_bias(df_1d, "1d") if df_1d is not None else "NEUTRAL"
    weekly_bias = get_higher_tf_bias(df_1w, "1w") if df_1w is not None else "NEUTRAL"

    htf_score, htf_reason = score_htf_alignment(daily_bias, weekly_bias, direction)

    context_score = round(btc_score + htf_score, 3)

    opposite = "SHORT" if direction == "LONG" else "LONG"
    both_opposing = daily_bias == opposite and weekly_bias == opposite

    size_mult = 1.0
    alignment = "none"

    if daily_bias == direction and weekly_bias == direction:
        size_mult = 1.3
        alignment = "strong"
    elif daily_bias == direction or weekly_bias == direction:
        size_mult = 1.0
        alignment = "normal"
    elif both_opposing:
        size_mult = 0.5
        alignment = "opposing"
    else:
        size_mult = 0.7
        alignment = "weak"

    if btc_score <= -8 and htf_score <= -5:
        record_scan(coin, direction, "btc_context")
        return {
            "pass":          False,
            "direction":     direction,
            "reason":        "btc_and_htf_both_strongly_opposing",
            "btc_score":     btc_score,
            "htf_score":     htf_score,
            "context_score": context_score,
            "alignment":     None,
            "trace": {
                "ema":  f"direction:{direction}",
                "btc":  btc_reason,
                "htf":  htf_reason,
            },
        }

    alignment_dict = {
        "pass":      True,
        "daily":     daily_bias,
        "weekly":    weekly_bias,
        "alignment": alignment,
        "size_mult": size_mult,
        "reason":    "",
    }

    return {
        "pass":          True,
        "direction":     direction,
        "reason":        "",
        "btc_score":     btc_score,
        "htf_score":     htf_score,
        "context_score": context_score,
        "alignment":     alignment_dict,
        "trace": {
            "ema":  f"direction:{direction}",
            "btc":  btc_reason,
            "htf":  htf_reason,
        },
    }