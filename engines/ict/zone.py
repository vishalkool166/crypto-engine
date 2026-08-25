import logging
import pandas as pd
from dataclasses import dataclass
from typing import Optional
from config import cfg

log = logging.getLogger(__name__)

HE = cfg.HYBRID_ENGINE


@dataclass
class ZoneData:
    type:         str
    top:          float
    bottom:       float
    mid:          float
    touch_count:  int
    in_zone:      bool
    score:        float
    distance_pct: float
    origin_desc:  str
    strength:     float
    timeframe:    str


@dataclass
class ZoneResult:
    detected: bool
    zone:     Optional[ZoneData]
    score:    float
    desc:     str


def detect(
    d4h:      dict,
    df_4h:    pd.DataFrame,
    d1h:      dict,
    df_1h:    pd.DataFrame,
    direction: str,
    atr_1h:   float,
) -> ZoneResult:
    price = float(d4h.get("price") or 0)
    if not price:
        return ZoneResult(detected=False, zone=None, score=0.0, desc="no_price")

    candidates = []

    ob_4h  = _find_ob_zone(d4h,  direction, price, atr_1h, "4h")
    fvg_4h = _find_fvg_zone(d4h, direction, price, atr_1h, "4h")
    ob_1h  = _find_ob_zone(d1h,  direction, price, atr_1h, "1h")
    fvg_1h = _find_fvg_zone(d1h, direction, price, atr_1h, "1h")

    for z in [ob_4h, fvg_4h, ob_1h, fvg_1h]:
        if z is not None:
            candidates.append(z)

    if not candidates:
        return ZoneResult(detected=False, zone=None, score=0.0, desc="no_zone_found")

    candidates.sort(key=lambda z: (-z.score, z.distance_pct))
    best = candidates[0]

    if best.score < HE["zone_min_score"]:
        return ZoneResult(detected=False, zone=None, score=best.score, desc=f"zone_score_low:{best.score:.3f}")

    return ZoneResult(
        detected = True,
        zone     = best,
        score    = best.score,
        desc     = best.origin_desc,
    )


def _find_ob_zone(
    d:         dict,
    direction: str,
    price:     float,
    atr_1h:    float,
    tf:        str,
) -> Optional[ZoneData]:
    try:
        ob_data = d.get("order_blocks", {})
        obs     = ob_data.get("bull_obs", []) if direction == "LONG" else ob_data.get("bear_obs", [])

        if not obs:
            return None

        candidates = []

        for ob in obs:
            if ob.get("mitigated"):
                continue
            if ob.get("touch_count", 0) > HE["zone_max_touches"]:
                continue

            top    = float(ob["top"])
            bottom = float(ob["bottom"])
            width  = top - bottom

            if width < atr_1h * HE["zone_min_width_atr"]:
                continue

            dist_pct = abs(price - (top + bottom) / 2) / price * 100
            if dist_pct > HE["zone_max_dist_pct"]:
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

            tf_mult = 1.0 if tf == "4h" else 0.85
            score   = round(score * tf_mult, 3)

            candidates.append(ZoneData(
                type         = "OB",
                top          = round(top, 6),
                bottom       = round(bottom, 6),
                mid          = round((top + bottom) / 2, 6),
                touch_count  = touch_count,
                in_zone      = bottom <= price <= top,
                score        = score,
                distance_pct = round(dist_pct, 3),
                origin_desc  = f"{tf} OB {bottom:.4f}-{top:.4f}",
                strength     = float(ob.get("strength", 0)),
                timeframe    = tf,
            ))

        if not candidates:
            return None

        candidates.sort(key=lambda z: (-z.score, z.distance_pct))
        return candidates[0]

    except Exception as e:
        log.error("_find_ob_zone %s: %s", tf, e)
        return None


def _find_fvg_zone(
    d:         dict,
    direction: str,
    price:     float,
    atr_1h:    float,
    tf:        str,
) -> Optional[ZoneData]:
    try:
        fvgs        = d.get("fvgs", [])
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
            if width < atr_1h * HE["zone_min_width_atr"]:
                continue

            dist_pct = abs(price - mid) / price * 100
            if dist_pct > HE["zone_max_dist_pct"]:
                continue

            score    = round(_width_score(width, atr_1h), 3)
            tf_mult  = 1.0 if tf == "4h" else 0.85
            score    = round(score * tf_mult, 3)

            if score < HE["zone_min_score"]:
                continue

            candidates.append(ZoneData(
                type         = "FVG",
                top          = round(top, 6),
                bottom       = round(bottom, 6),
                mid          = round(mid, 6),
                touch_count  = 0,
                in_zone      = bottom <= price <= top,
                score        = score,
                distance_pct = round(dist_pct, 3),
                origin_desc  = f"{tf} FVG {bottom:.4f}-{top:.4f}",
                strength     = score,
                timeframe    = tf,
            ))

        if not candidates:
            return None

        candidates.sort(key=lambda z: z.distance_pct)
        return candidates[0]

    except Exception as e:
        log.error("_find_fvg_zone %s: %s", tf, e)
        return None


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