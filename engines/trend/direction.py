import logging
from dataclasses import dataclass
from config import cfg

log = logging.getLogger(__name__)


@dataclass
class TrendResult:
    direction: str
    adx:       float
    ema20:     float
    ema50:     float
    ema200:    float
    passed:    bool
    reason:    str


def detect(d4h: dict, coin: str) -> TrendResult:
    from data.rejection_stats import record_scan

    price  = float(d4h.get("price")  or 0)
    ema20  = float(d4h.get("ema20")  or 0)
    ema50  = float(d4h.get("ema50")  or 0)
    ema200 = float(d4h.get("ema200") or 0)
    adx    = float(d4h.get("adx")    or 0)
    atr    = float(d4h.get("atr")    or price * 0.01)

    min_adx = cfg.HYBRID_ENGINE.get("trend_min_adx", 18)
    buffer  = atr * cfg.HYBRID_ENGINE.get("trend_ema_buffer_atr_mult", 0.05)

    if adx < min_adx:
        record_scan(coin, "NEUTRAL", "adx_too_low")
        return _rejected("adx_too_low", adx, ema20, ema50, ema200)

    if not price or not ema200:
        record_scan(coin, "NEUTRAL", "missing_indicators")
        return _rejected("missing_indicators", adx, ema20, ema50, ema200)

    if price > ema200:
        direction = "LONG"
    elif price < ema200:
        direction = "SHORT"
    else:
        record_scan(coin, "NEUTRAL", "ema_neutral")
        return _rejected("ema_neutral", adx, ema20, ema50, ema200)

    if ema20 and ema50:
        if direction == "LONG":
            strict = price > ema20 + buffer and ema20 > ema50
            relaxed = price > ema20 + buffer * 2
            if not strict and not relaxed:
                record_scan(coin, "NEUTRAL", "ema_neutral")
                return _rejected("ema_neutral", adx, ema20, ema50, ema200)
        else:
            strict = price < ema20 - buffer and ema20 < ema50
            relaxed = price < ema20 - buffer * 2
            if not strict and not relaxed:
                record_scan(coin, "NEUTRAL", "ema_neutral")
                return _rejected("ema_neutral", adx, ema20, ema50, ema200)

    return TrendResult(
        direction = direction,
        adx       = round(adx, 2),
        ema20     = round(ema20, 6),
        ema50     = round(ema50, 6),
        ema200    = round(ema200, 6),
        passed    = True,
        reason    = "",
    )


def _rejected(
    reason: str,
    adx:    float,
    ema20:  float,
    ema50:  float,
    ema200: float,
) -> TrendResult:
    return TrendResult(
        direction = "NEUTRAL",
        adx       = round(adx, 2),
        ema20     = round(ema20, 6),
        ema50     = round(ema50, 6),
        ema200    = round(ema200, 6),
        passed    = False,
        reason    = reason,
    )