import logging
from dataclasses import dataclass
from config import cfg

log = logging.getLogger(__name__)


@dataclass
class RegimeResult:
    label:       str
    size_mult:   float
    adx:         float
    atr_pct:     float
    is_trending: bool
    is_ranging:  bool
    is_choppy:   bool
    is_volatile: bool
    reason:      str


def detect(d4h: dict, d1w: dict = None) -> RegimeResult:
    adx     = float(d4h.get("adx")   or 0)
    atr     = float(d4h.get("atr")   or 0)
    price   = float(d4h.get("price") or 1)
    atr_pct = round(atr / price * 100, 4) if price > 0 else 0.0

    if atr_pct > 4.0:
        return RegimeResult(
            label       = "volatile",
            size_mult   = 0.3,
            adx         = round(adx, 2),
            atr_pct     = atr_pct,
            is_trending = False,
            is_ranging  = False,
            is_choppy   = False,
            is_volatile = True,
            reason      = f"atr_pct:{atr_pct:.2f}%",
        )

    if adx >= 25:
        return RegimeResult(
            label       = "trending",
            size_mult   = 1.0,
            adx         = round(adx, 2),
            atr_pct     = atr_pct,
            is_trending = True,
            is_ranging  = False,
            is_choppy   = False,
            is_volatile = False,
            reason      = f"adx:{adx:.1f}",
        )

    if adx >= 20:
        return RegimeResult(
            label       = "ranging",
            size_mult   = 0.7,
            adx         = round(adx, 2),
            atr_pct     = atr_pct,
            is_trending = False,
            is_ranging  = True,
            is_choppy   = False,
            is_volatile = False,
            reason      = f"adx:{adx:.1f}",
        )

    return RegimeResult(
        label       = "choppy",
        size_mult   = 0.5,
        adx         = round(adx, 2),
        atr_pct     = atr_pct,
        is_trending = False,
        is_ranging  = False,
        is_choppy   = True,
        is_volatile = False,
        reason      = f"adx:{adx:.1f}",
    )