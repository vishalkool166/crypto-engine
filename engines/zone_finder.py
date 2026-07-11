import time
import logging
from config import cfg

log = logging.getLogger(__name__)


def get_active_zone(d4h: dict, direction: str) -> dict | None:
    se    = cfg.SIGNAL_ENGINE
    price = d4h.get("price", 0)
    atr   = d4h.get("atr") or price * 0.015

    if not price:
        return None

    max_distance = max(
        atr / price * 100 * se["zone_distance_atr_mult"],
        se["zone_distance_min_pct"]
    )

    ob_zone  = _find_ob_zone(d4h, direction, price, se)
    fvg_zone = _find_fvg_zone(d4h, direction, price, atr, se)
    zone     = _select_zone(ob_zone, fvg_zone, price)

    if not zone:
        return None

    distance_pct = abs(price - zone["mid"]) / price * 100
    if distance_pct > max_distance:
        return None

    zone["distance_pct"]  = round(distance_pct, 3)
    zone["max_distance"]  = round(max_distance, 3)
    zone["atr"]           = round(atr, 6)
    zone["evaluated_at"]  = time.time()
    return zone


def _find_ob_zone(
    d4h:       dict,
    direction: str,
    price:     float,
    se:        dict
) -> dict | None:
    ob_data = d4h.get("order_blocks", {})

    ob = (
        ob_data.get("nearest_bull")
        if direction == "LONG"
        else ob_data.get("nearest_bear")
    )

    if not ob:
        return None
    if ob.get("mitigated"):
        return None
    if ob.get("weak"):
        return None
    if ob.get("touch_count", 0) > se["zone_max_touches"]:
        return None

    return {
        "type":        "OB",
        "direction":   direction,
        "top":         ob["top"],
        "bottom":      ob["bottom"],
        "mid":         ob["mid"],
        "touch_count": ob.get("touch_count", 0),
        "strength":    ob.get("strength", 0),
        "in_zone":     ob.get("in_zone", False),
        "approaching": ob.get("approaching", False),
        "label":       ob.get("label", "Order Block"),
        "desc":        ob.get("desc", ""),
    }


def _find_fvg_zone(
    d4h:       dict,
    direction: str,
    price:     float,
    atr:       float,
    se:        dict
) -> dict | None:
    fvgs        = d4h.get("fvgs", [])
    target_type = "bull" if direction == "LONG" else "bear"
    candidates  = []

    for fvg in fvgs:
        if fvg.get("type") != target_type:
            continue

        top    = fvg.get("top",    0)
        bottom = fvg.get("bottom", 0)
        mid    = fvg.get("mid",    0)

        if not top or not bottom or not mid:
            continue

        width_pct = (top - bottom) / price * 100
        if width_pct < se["fvg_min_width_pct"]:
            continue

        min_width_atr = atr / price * 100 * 0.3
        if width_pct < min_width_atr:
            continue

        dist = abs(price - mid) / price * 100

        candidates.append({
            "type":        "FVG",
            "direction":   direction,
            "top":         top,
            "bottom":      bottom,
            "mid":         mid,
            "touch_count": 0,
            "strength":    round(width_pct, 3),
            "in_zone":     bottom <= price <= top,
            "approaching": True,
            "label":       f"{'Bullish' if direction == 'LONG' else 'Bearish'} FVG",
            "desc":        f"FVG {bottom:.4f}-{top:.4f}",
            "dist":        dist,
        })

    if not candidates:
        return None

    candidates.sort(key=lambda x: x["dist"])
    best = candidates[0]
    best.pop("dist", None)
    return best


def _select_zone(
    ob_zone:  dict | None,
    fvg_zone: dict | None,
    price:    float
) -> dict | None:
    if not ob_zone and not fvg_zone:
        return None

    if ob_zone and not fvg_zone:
        return ob_zone

    if fvg_zone and not ob_zone:
        return fvg_zone

    if ob_zone["in_zone"]:
        return ob_zone
    if fvg_zone["in_zone"]:
        return fvg_zone

    ob_dist  = abs(price - ob_zone["mid"])  / price * 100
    fvg_dist = abs(price - fvg_zone["mid"]) / price * 100

    return ob_zone if ob_dist <= fvg_dist else fvg_zone