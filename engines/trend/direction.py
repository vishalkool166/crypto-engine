import logging
from dataclasses import dataclass
from typing import Optional
from config import cfg

log = logging.getLogger(__name__)

HE = cfg.HYBRID_ENGINE


@dataclass
class TrendResult:
    direction:     str
    strength:      float
    adx:           float
    ema20:         float
    ema50:         float
    ema200:        float
    daily_bias:    str
    weekly_bias:   str
    alignment:     str
    size_mult:     float
    btc_score:     float
    htf_score:     float
    context_score: float
    passed:        bool
    reason:        str
    trace:         dict


def detect(
    d4h:  dict,
    coin: str,
    df_1d=None,
    df_1w=None,
) -> TrendResult:
    from data.rejection_stats import record_scan

    adx   = float(d4h.get("adx") or 0)
    price = float(d4h.get("price") or 0)
    ema20 = float(d4h.get("ema20") or 0)
    ema50 = float(d4h.get("ema50") or 0)
    ema200= float(d4h.get("ema200") or 0)
    atr   = float(d4h.get("atr") or price * 0.01)

    min_adx = HE["trend_min_adx"]
    buffer  = atr * HE["trend_ema_buffer_atr_mult"]

    if adx < min_adx:
        record_scan(coin, "NEUTRAL", "adx_too_low")
        return _rejected(
            reason  = "adx_too_low",
            adx     = adx,
            ema20   = ema20,
            ema50   = ema50,
            ema200  = ema200,
            trace   = {"ema": f"ADX {adx:.1f} below min {min_adx}"},
        )

    direction = _get_4h_direction(price, ema20, ema50, buffer)

    if direction == "NEUTRAL":
        record_scan(coin, "NEUTRAL", "ema_neutral")
        return _rejected(
            reason = "ema_neutral",
            adx    = adx,
            ema20  = ema20,
            ema50  = ema50,
            ema200 = ema200,
            trace  = {"ema": "4H EMA not aligned"},
        )

    daily_bias  = _get_htf_bias(df_1d, "1d")
    weekly_bias = _get_htf_bias(df_1w, "1w")

    opposite = "SHORT" if direction == "LONG" else "LONG"
    if daily_bias == opposite and weekly_bias == opposite:
        record_scan(coin, direction, "htf_opposing")
        return _rejected(
            reason = "htf_opposing",
            adx    = adx,
            ema20  = ema20,
            ema50  = ema50,
            ema200 = ema200,
            trace  = {"ema": f"{direction}", "htf": "daily+weekly both opposing"},
        )

    btc_score, btc_reason = _score_btc(direction)

    if btc_score <= -8.0:
        record_scan(coin, direction, "btc_opposing")
        return _rejected(
            reason = "btc_opposing",
            adx    = adx,
            ema20  = ema20,
            ema50  = ema50,
            ema200 = ema200,
            trace  = {"ema": direction, "btc": btc_reason},
        )

    htf_score, htf_reason   = _score_htf(daily_bias, weekly_bias, direction)
    context_score           = round(btc_score + htf_score, 3)
    alignment, size_mult    = _get_alignment(daily_bias, weekly_bias, direction)

    return TrendResult(
        direction     = direction,
        strength      = round(adx, 2),
        adx           = round(adx, 2),
        ema20         = round(ema20, 6),
        ema50         = round(ema50, 6),
        ema200        = round(ema200, 6),
        daily_bias    = daily_bias,
        weekly_bias   = weekly_bias,
        alignment     = alignment,
        size_mult     = size_mult,
        btc_score     = btc_score,
        htf_score     = htf_score,
        context_score = context_score,
        passed        = True,
        reason        = "",
        trace         = {
            "ema": f"direction:{direction} adx:{adx:.1f}",
            "btc": btc_reason,
            "htf": htf_reason,
        },
    )


def _get_4h_direction(
    price:  float,
    ema20:  float,
    ema50:  float,
    buffer: float,
) -> str:
    if not price or not ema20 or not ema50:
        return "NEUTRAL"

    if price > ema20 + buffer and ema20 > ema50:
        return "LONG"

    if price < ema20 - buffer and ema20 < ema50:
        return "SHORT"

    if price < ema20 - buffer * 2:
        return "SHORT"

    if price > ema20 + buffer * 2:
        return "LONG"

    return "NEUTRAL"


def _get_htf_bias(df, tf: str) -> str:
    if df is None or len(df) < 20:
        return "NEUTRAL"
    try:
        from engines.indicators import calculate_all
        from config import cfg
        d    = calculate_all(df, timeframe=tf)
        p    = float(d.get("price") or 0)
        e20  = float(d.get("ema20") or 0)
        e50  = float(d.get("ema50") or 0)
        atr  = float(d.get("atr") or p * 0.01)
        buf  = atr * HE["trend_ema_buffer_atr_mult"]
        if not p or not e20 or not e50:
            return "NEUTRAL"
        if p > e20 + buf and e20 > e50:
            return "LONG"
        if p < e20 - buf and e20 < e50:
            return "SHORT"
        return "NEUTRAL"
    except Exception as e:
        log.warning("_get_htf_bias %s: %s", tf, e)
        return "NEUTRAL"


def _score_btc(direction: str) -> tuple[float, str]:
    try:
        from data.cache import cache
        from config import BTC_CONTEXT_SCORES
        btc = cache.get_raw("btc_4h_data")
        if not btc:
            return 5.0, "BTC data unavailable — neutral"

        btc_cls = btc.get("trend", {}).get("cls", "neutral")
        btc_adx = float(btc.get("adx") or 0)
        scores  = BTC_CONTEXT_SCORES
        is_long = direction == "LONG"

        if btc_cls == "neutral":
            return 5.0, "BTC neutral"

        if is_long:
            if btc_cls == "bull":
                score = scores["strongly_aligned"] if btc_adx >= scores["adx_strong_threshold"] else scores["aligned"]
                return float(score), f"BTC bullish ADX:{btc_adx:.0f}"
            else:
                if btc_adx >= scores["adx_panic_threshold"]:
                    return float(scores["strongly_opposing"]), f"BTC strongly bearish ADX:{btc_adx:.0f}"
                if btc_adx >= scores["adx_moderate_threshold"]:
                    return float(scores["opposing"]), f"BTC bearish ADX:{btc_adx:.0f}"
                return float(scores["weakly_opposing"]), f"BTC weakly bearish ADX:{btc_adx:.0f}"
        else:
            if btc_cls == "bear":
                score = scores["strongly_aligned"] if btc_adx >= scores["adx_strong_threshold"] else scores["aligned"]
                return float(score), f"BTC bearish ADX:{btc_adx:.0f}"
            else:
                if btc_adx >= scores["adx_panic_threshold"]:
                    return float(scores["strongly_opposing"]), f"BTC strongly bullish ADX:{btc_adx:.0f}"
                if btc_adx >= scores["adx_moderate_threshold"]:
                    return float(scores["opposing"]), f"BTC bullish ADX:{btc_adx:.0f}"
                return float(scores["weakly_opposing"]), f"BTC weakly bullish ADX:{btc_adx:.0f}"

    except Exception as e:
        log.warning("_score_btc: %s", e)
        return 5.0, "BTC score error — neutral"


def _score_htf(daily_bias: str, weekly_bias: str, direction: str) -> tuple[float, str]:
    from config import HTF_ALIGNMENT_SCORES
    scores   = HTF_ALIGNMENT_SCORES
    opposite = "SHORT" if direction == "LONG" else "LONG"

    daily_match  = daily_bias  == direction
    weekly_match = weekly_bias == direction
    daily_opp    = daily_bias  == opposite
    weekly_opp   = weekly_bias == opposite

    if daily_opp and weekly_opp:
        return float(scores["both_opposing"]), "Daily and weekly both opposing"
    if daily_opp:
        return float(scores["one_opposing"]), "Daily opposing"
    if weekly_opp:
        return float(scores["one_opposing"]), "Weekly opposing"
    if daily_match and weekly_match:
        return float(scores["both_aligned"]), "Daily and weekly both aligned"
    if daily_match or weekly_match:
        return float(scores["one_aligned"]), "One timeframe aligned"
    return float(scores["both_neutral"]), "Both timeframes neutral"


def _get_alignment(
    daily_bias:  str,
    weekly_bias: str,
    direction:   str,
) -> tuple[str, float]:
    opposite = "SHORT" if direction == "LONG" else "LONG"

    if daily_bias == direction and weekly_bias == direction:
        return "strong", 1.3
    if daily_bias == opposite and weekly_bias == opposite:
        return "opposing", 0.5
    if daily_bias == direction or weekly_bias == direction:
        return "normal", 1.0
    return "weak", 0.7


def _rejected(
    reason: str,
    adx:    float,
    ema20:  float,
    ema50:  float,
    ema200: float = 0.0,
    trace:  dict  = None,
) -> TrendResult:
    return TrendResult(
        direction     = "NEUTRAL",
        strength      = round(adx, 2),
        adx           = round(adx, 2),
        ema20         = round(ema20, 6),
        ema50         = round(ema50, 6),
        ema200        = round(ema200, 6),
        daily_bias    = "NEUTRAL",
        weekly_bias   = "NEUTRAL",
        alignment     = "none",
        size_mult     = 0.0,
        btc_score     = 0.0,
        htf_score     = 0.0,
        context_score = 0.0,
        passed        = False,
        reason        = reason,
        trace         = trace or {},
    )