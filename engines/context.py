import logging
from engines.indicators import calculate_all
from engines.scorer import score_btc_context, score_htf_alignment, SignalScore
from config import cfg

log = logging.getLogger(__name__)

SE = cfg.SCALP_ENGINE


def get_direction(d4h: dict, d1d: dict = None) -> str:
    price = d4h.get("price", 0)
    ema20 = d4h.get("ema20")
    ema50 = d4h.get("ema50")
    atr   = d4h.get("atr")

    if not price or not ema20 or not ema50 or not atr:
        return "NEUTRAL"

    buffer = atr * SE["ema_buffer_atr_mult"]

    if price > ema20 + buffer and ema20 > ema50:
        h4_direction = "LONG"
    elif price < ema20 - buffer and ema20 < ema50:
        h4_direction = "SHORT"
    else:
        return "NEUTRAL"

    if d1d is not None:
        d1_trend = d1d.get("trend", {}).get("cls", "neutral")
        if h4_direction == "LONG" and d1_trend == "bear":
            return "NEUTRAL"
        if h4_direction == "SHORT" and d1_trend == "bull":
            return "NEUTRAL"

    return h4_direction


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


def _is_asia_session() -> bool:
    from datetime import datetime, timezone
    hour = datetime.now(timezone.utc).hour
    return 0 <= hour < 8


def _get_adx(d4h: dict) -> float:
    return float(d4h.get("adx") or 0)


def check(
    d4h:   dict,
    coin:  str,
    df_1d=None,
    df_1w=None,
) -> dict:
    from data.rejection_stats import record_scan

    if _is_asia_session():
        record_scan(coin, "NEUTRAL", "asia_session_blocked")
        return {
            "pass":          False,
            "direction":     "NEUTRAL",
            "reason":        "asia_session_blocked",
            "btc_score":     0.0,
            "htf_score":     0.0,
            "context_score": 0.0,
            "alignment":     None,
            "trace": {
                "ema": "BLOCKED — Asia session",
                "btc": "skipped",
                "htf": "skipped",
            },
        }

    adx = _get_adx(d4h)
    min_adx = SE.get("min_adx", 20)
    if adx < min_adx:
        record_scan(coin, "NEUTRAL", "adx_too_low")
        return {
            "pass":          False,
            "direction":     "NEUTRAL",
            "reason":        "adx_too_low",
            "btc_score":     0.0,
            "htf_score":     0.0,
            "context_score": 0.0,
            "alignment":     None,
            "trace": {
                "ema": f"BLOCKED — ADX {adx:.1f} below minimum {min_adx}",
                "btc": "skipped",
                "htf": "skipped",
            },
        }

    d1d_indicators = None
    if df_1d is not None and len(df_1d) >= 20:
        try:
            d1d_indicators = calculate_all(df_1d, timeframe="1d")
        except Exception as e:
            log.warning("1D indicators error %s: %s", coin, e)

    direction = get_direction(d4h, d1d_indicators)

    if direction == "NEUTRAL":
        record_scan(coin, "NEUTRAL", "ema_neutral")
        return {
            "pass":          False,
            "direction":     "NEUTRAL",
            "reason":        "ema_neutral",
            "btc_score":     0.0,
            "htf_score":     0.0,
            "context_score": 0.0,
            "alignment":     None,
            "trace": {
                "ema":  "NEUTRAL — 4H and 1D not aligned",
                "btc":  "skipped",
                "htf":  "skipped",
            },
        }

    btc = get_btc_context()

    if btc["available"]:
        btc_cls = btc["cls"]
        btc_adx = btc["adx"]
        opposite = "SHORT" if direction == "LONG" else "LONG"

        if direction == "LONG" and btc_cls == "bear" and btc_adx >= 25:
            record_scan(coin, direction, "btc_opposing")
            return {
                "pass":          False,
                "direction":     direction,
                "reason":        "btc_opposing",
                "btc_score":     -8.0,
                "htf_score":     0.0,
                "context_score": -8.0,
                "alignment":     None,
                "trace": {
                    "ema": f"direction:{direction}",
                    "btc": f"BLOCKED — BTC bearish ADX:{btc_adx:.0f}",
                    "htf": "skipped",
                },
            }

        if direction == "SHORT" and btc_cls == "bull" and btc_adx >= 25:
            record_scan(coin, direction, "btc_opposing")
            return {
                "pass":          False,
                "direction":     direction,
                "reason":        "btc_opposing",
                "btc_score":     -8.0,
                "htf_score":     0.0,
                "context_score": -8.0,
                "alignment":     None,
                "trace": {
                    "ema": f"direction:{direction}",
                    "btc": f"BLOCKED — BTC bullish ADX:{btc_adx:.0f}",
                    "htf": "skipped",
                },
            }

    btc_score, btc_reason = score_btc_context(
        btc["cls"], btc["adx"], direction
    )

    daily_bias  = get_higher_tf_bias(df_1d, "1d") if df_1d is not None else "NEUTRAL"
    weekly_bias = get_higher_tf_bias(df_1w, "1w") if df_1w is not None else "NEUTRAL"

    htf_score, htf_reason = score_htf_alignment(daily_bias, weekly_bias, direction)

    context_score = round(btc_score + htf_score, 3)

    opposite      = "SHORT" if direction == "LONG" else "LONG"
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
            "ema":  f"direction:{direction} adx:{adx:.1f}",
            "btc":  btc_reason,
            "htf":  htf_reason,
        },
    }