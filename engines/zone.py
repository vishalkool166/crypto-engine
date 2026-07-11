import logging
import pandas as pd
from config import cfg

log = logging.getLogger(__name__)

SE = cfg.SCALP_ENGINE


def _count_touches(df: pd.DataFrame, top: float, bottom: float) -> int:
    touches = 0
    for _, c in df.iterrows():
        if float(c["low"]) <= top and float(c["high"]) >= bottom:
            touches += 1
    return touches


def _find_ob_zone(d4h: dict, direction: str, price: float, atr_1h: float) -> dict | None:
    try:
        ob_data = d4h.get("order_blocks", {})
        ob      = ob_data.get("nearest_bull") if direction == "LONG" else ob_data.get("nearest_bear")

        if not ob:
            return None
        if ob.get("mitigated"):
            return None
        if ob.get("touch_count", 0) > SE["zone_max_touches"]:
            return None

        top    = float(ob["top"])
        bottom = float(ob["bottom"])
        width  = top - bottom

        if width < atr_1h * SE["zone_min_width_atr"]:
            return None

        dist = abs(price - (top + bottom) / 2) / price
        if dist > (atr_1h / price) * SE["zone_max_dist_atr"]:
            return None

        if direction == "LONG" and price < bottom:
            return None
        if direction == "SHORT" and price > top:
            return None

        touch_mult = (
            1.0  if ob.get("touch_count", 0) == 0 else
            0.75 if ob.get("touch_count", 0) == 1 else
            0.40
        )
        width_score = min(width / atr_1h, 2.0) / 2.0
        score       = round(width_score * touch_mult, 3)

        if score < SE["zone_min_score"]:
            return None

        return {
            "type":        "OB",
            "top":         round(top, 6),
            "bottom":      round(bottom, 6),
            "mid":         round((top + bottom) / 2, 6),
            "touch_count": ob.get("touch_count", 0),
            "in_zone":     bottom <= price <= top,
            "strength":    ob.get("strength", 0),
            "score":       score,
            "origin_desc": f"Order block {bottom:.4f}–{top:.4f}",
        }
    except Exception as e:
        log.error("_find_ob_zone: %s", e)
        return None


def _find_fvg_zone(d4h: dict, direction: str, price: float, atr_1h: float) -> dict | None:
    try:
        fvgs        = d4h.get("fvgs", [])
        target_type = "bull" if direction == "LONG" else "bear"
        candidates  = []

        for fvg in fvgs:
            if fvg.get("type") != target_type:
                continue

            top    = float(fvg.get("top",    0))
            bottom = float(fvg.get("bottom", 0))
            mid    = float(fvg.get("mid",    0))

            if not top or not bottom or not mid:
                continue

            if direction == "LONG" and price < bottom:
                continue
            if direction == "SHORT" and price > top:
                continue

            width = top - bottom
            if width < atr_1h * SE["zone_min_width_atr"]:
                continue

            dist = abs(price - mid) / price
            if dist > (atr_1h / price) * SE["zone_max_dist_atr"]:
                continue

            width_score = min(width / atr_1h, 2.0) / 2.0
            score       = round(width_score, 3)

            if score < SE["zone_min_score"]:
                continue

            candidates.append({
                "type":        "FVG",
                "top":         round(top, 6),
                "bottom":      round(bottom, 6),
                "mid":         round(mid, 6),
                "touch_count": 0,
                "in_zone":     bottom <= price <= top,
                "strength":    round(width_score, 3),
                "score":       score,
                "dist":        dist,
                "origin_desc": f"Fair value gap {bottom:.4f}–{top:.4f}",
            })

        if not candidates:
            return None

        candidates.sort(key=lambda x: x["dist"])
        best = candidates[0]
        best.pop("dist", None)
        return best

    except Exception as e:
        log.error("_find_fvg_zone: %s", e)
        return None


def detect(d4h: dict, df_4h: pd.DataFrame, direction: str, atr_1h: float) -> dict:
    try:
        price = d4h.get("price", 0)

        if not price:
            return {"detected": False, "zone": None, "score": 0.0}

        ob_zone  = _find_ob_zone(d4h,  direction, price, atr_1h)
        fvg_zone = _find_fvg_zone(d4h, direction, price, atr_1h)

        if not ob_zone and not fvg_zone:
            return {"detected": False, "zone": None, "score": 0.0}

        if ob_zone and fvg_zone:
            ob_dist  = abs(price - ob_zone["mid"])  / price
            fvg_dist = abs(price - fvg_zone["mid"]) / price
            zone     = ob_zone if ob_dist <= fvg_dist else fvg_zone
        else:
            zone = ob_zone or fvg_zone

        distance_pct = abs(price - zone["mid"]) / price * 100
        max_dist_pct = (atr_1h / price) * SE["zone_max_dist_atr"] * 100

        zone["distance_pct"] = round(distance_pct, 3)
        zone["max_dist_pct"] = round(max_dist_pct, 3)

        return {
            "detected": True,
            "zone":     zone,
            "score":    zone["score"],
        }

    except Exception as e:
        log.error("zone.detect %s: %s", direction, e)
        return {"detected": False, "zone": None, "score": 0.0}