from dataclasses import dataclass


@dataclass
class RegimeResult:
    label:       str
    is_trending: bool
    is_ranging:  bool
    is_volatile: bool
    adx:         float
    atr_pct:     float
    size_mult:   float


def detect_regime(d: dict) -> RegimeResult:
    adx     = float(d.get("adx")   or 0)
    atr     = float(d.get("atr")   or 0)
    price   = float(d.get("price") or 1)
    atr_pct = round(atr / price * 100, 4) if price > 0 else 0.0

    if atr_pct > 4.0:
        return RegimeResult(
            label       = "volatile",
            is_trending = False,
            is_ranging  = False,
            is_volatile = True,
            adx         = round(adx, 2),
            atr_pct     = atr_pct,
            size_mult   = 0.3,
        )

    if adx >= 20:
        return RegimeResult(
            label       = "trending",
            is_trending = True,
            is_ranging  = False,
            is_volatile = False,
            adx         = round(adx, 2),
            atr_pct     = atr_pct,
            size_mult   = 1.0,
        )

    return RegimeResult(
        label       = "ranging",
        is_trending = False,
        is_ranging  = True,
        is_volatile = False,
        adx         = round(adx, 2),
        atr_pct     = atr_pct,
        size_mult   = 0.7,
    )