import logging
from dataclasses import dataclass
from config import cfg

log = logging.getLogger(__name__)

HE = cfg.HYBRID_ENGINE


@dataclass
class RegimeResult:
    label:        str
    size_mult:    float
    adx:          float
    atr_pct:      float
    trend_cls:    str
    is_trending:  bool
    is_ranging:   bool
    is_choppy:    bool
    is_volatile:  bool
    reason:       str


def detect(d4h: dict, d1w: dict = None) -> RegimeResult:
    adx       = float(d4h.get("adx") or 0)
    atr       = float(d4h.get("atr") or 0)
    price     = float(d4h.get("price") or 1)
    trend_cls = d4h.get("trend", {}).get("cls", "neutral")
    atr_pct   = (atr / price * 100) if price > 0 else 0.0

    adx_trending = HE["regime_adx_trending"]
    adx_ranging  = HE["regime_adx_ranging"]

    volatile = _is_volatile(atr_pct, adx, d1w)

    if volatile:
        return RegimeResult(
            label       = "volatile",
            size_mult   = HE["regime_size_volatile"],
            adx         = round(adx, 2),
            atr_pct     = round(atr_pct, 4),
            trend_cls   = trend_cls,
            is_trending = False,
            is_ranging  = False,
            is_choppy   = False,
            is_volatile = True,
            reason      = f"atr_pct:{atr_pct:.2f}% adx:{adx:.1f}",
        )

    if adx >= adx_trending and trend_cls in ("bull", "bear"):
        return RegimeResult(
            label       = "trending",
            size_mult   = HE["regime_size_trending"],
            adx         = round(adx, 2),
            atr_pct     = round(atr_pct, 4),
            trend_cls   = trend_cls,
            is_trending = True,
            is_ranging  = False,
            is_choppy   = False,
            is_volatile = False,
            reason      = f"adx:{adx:.1f} trend:{trend_cls}",
        )

    if adx_ranging <= adx < adx_trending:
        return RegimeResult(
            label       = "ranging",
            size_mult   = HE["regime_size_ranging"],
            adx         = round(adx, 2),
            atr_pct     = round(atr_pct, 4),
            trend_cls   = trend_cls,
            is_trending = False,
            is_ranging  = True,
            is_choppy   = False,
            is_volatile = False,
            reason      = f"adx:{adx:.1f} between thresholds",
        )

    return RegimeResult(
        label       = "choppy",
        size_mult   = HE["regime_size_choppy"],
        adx         = round(adx, 2),
        atr_pct     = round(atr_pct, 4),
        trend_cls   = trend_cls,
        is_trending = False,
        is_ranging  = False,
        is_choppy   = True,
        is_volatile = False,
        reason      = f"adx:{adx:.1f} below ranging threshold",
    )


def _is_volatile(atr_pct: float, adx: float, d1w: dict = None) -> bool:
    if atr_pct > 4.0:
        return True

    if d1w:
        w_atr   = float(d1w.get("atr") or 0)
        w_price = float(d1w.get("price") or 1)
        w_atr_pct = (w_atr / w_price * 100) if w_price > 0 else 0.0
        if w_atr_pct > 8.0:
            return True

    return False


def get_regime_grade_thresholds(regime_label: str) -> dict:
    from config import SCORE_THRESHOLDS
    mapping = {
        "trending": SCORE_THRESHOLDS["trending"],
        "ranging":  SCORE_THRESHOLDS["ranging"],
        "choppy":   SCORE_THRESHOLDS["choppy"],
        "volatile": SCORE_THRESHOLDS["volatile"],
    }
    return mapping.get(regime_label, SCORE_THRESHOLDS["default"])