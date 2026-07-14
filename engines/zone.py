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


def _width_score(width: float, atr_1h: float) -> float:
    if atr_1h <= 0:
        return 0.5
    ratio = width / atr_1h
    if ratio <= 0:
        return 0.0
    if ratio <= 1.0:
        return ratio * 0.5
    if ratio <= 3.0:
        return 0.5 + (ratio - 1.0) / 4.0
    return max(0.5, 1.0 - (ratio - 3.0) * 0.1)


def _find_ob_zone(d4h: dict, direction: str, price: float, atr_1h: float) -> dict | None:
    try:
        ob_data = d4h.get("order_blocks", {})

        if direction == "LONG":
            all_obs = ob_data.get("bull_obs", [])
        else:
            all_obs = ob_data.get("bear_obs", [])

        if not all_obs:
            return None

        candidates = []

        for ob in all_obs:
            if ob.get("mitigated"):
                continue

            if ob.get("touch_count", 0) > SE["zone_max_touches"]:
                continue

            top    = float(ob["top"])
            bottom = float(ob["bottom"])
            width  = top - bottom

            if width < atr_1h * SE["zone_min_width_atr"]:
                continue

            dist_pct = abs(price - (top + bottom) / 2) / price * 100
            if dist_pct > SE["zone_max_dist_pct"]:
                continue

            if direction == "LONG" and price < bottom:
                continue
            if direction == "SHORT" and price > top:
                continue

            touch_count = ob.get("touch_count", 0)
            touch_mult  = (
                1.0  if touch_count == 0 else
                0.75 if touch_count == 1 else
                0.50 if touch_count == 2 else
                0.30
            )

            score = round(_width_score(width, atr_1h) * touch_mult, 3)

            candidates.append({
                "type":        "OB",
                "top":         round(top, 6),
                "bottom":      round(bottom, 6),
                "mid":         round((top + bottom) / 2, 6),
                "touch_count": touch_count,
                "in_zone":     bottom <= price <= top,
                "strength":    ob.get("strength", 0),
                "score":       score,
                "dist_pct":    dist_pct,
                "origin_desc": "Order block {:.4f}-{:.4f}".format(bottom, top),
            })

        if not candidates:
            return None

        candidates.sort(key=lambda x: (-x["score"], x["dist_pct"]))
        best = candidates[0]

        if best["score"] < SE["zone_min_score"]:
            return None

        best.pop("dist_pct", None)
        return best

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

            dist_pct = abs(price - mid) / price * 100
            if dist_pct > SE["zone_max_dist_pct"]:
                continue

            score = round(_width_score(width, atr_1h), 3)

            if score < SE["zone_min_score"]:
                continue

            candidates.append({
                "type":        "FVG",
                "top":         round(top, 6),
                "bottom":      round(bottom, 6),
                "mid":         round(mid, 6),
                "touch_count": 0,
                "in_zone":     bottom <= price <= top,
                "strength":    round(_width_score(width, atr_1h), 3),
                "score":       score,
                "dist_pct":    dist_pct,
                "origin_desc": f"Fair value gap {bottom:.4f}–{top:.4f}",
            })

        if not candidates:
            return None

        candidates.sort(key=lambda x: x["dist_pct"])
        best = candidates[0]
        best.pop("dist_pct", None)
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
        max_dist_pct = SE["zone_max_dist_pct"]

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