import time
import logging
from config import cfg

log = logging.getLogger(__name__)


def build_signal(coin: str, context: dict, d1h: dict, d4h: dict) -> dict | None:
    se        = cfg.SIGNAL_ENGINE
    direction = context["direction"]
    is_long   = direction == "LONG"
    zone      = context["zone"]
    trigger   = context["trigger_pattern"]
    entry     = float(context["entry_price"])
    bias      = context["bias"]
    price     = entry

    atr_4h = d4h.get("atr") or price * 0.015
    atr_1h = d1h.get("atr") or atr_4h * 0.5

    sl = _calculate_sl(
        is_long   = is_long,
        entry     = entry,
        zone      = zone,
        trigger   = context,
        atr_4h    = atr_4h,
        se        = se
    )

    if sl is None:
        log.warning("%s signal rejected — SL calculation failed", coin)
        return None

    sl_dist = abs(entry - sl)
    sl_pct  = sl_dist / entry * 100

    if sl_pct < 0.2:
        log.warning("%s signal rejected — SL too tight: %.3f%%", coin, sl_pct)
        return None

    if sl_pct > 8.0:
        log.warning("%s signal rejected — SL too wide: %.3f%%", coin, sl_pct)
        return None

    tp1, tp1_label = _calculate_tp1(is_long, entry, sl_dist, d1h, d4h, se)
    tp2, tp2_label = _calculate_tp2(is_long, entry, sl_dist, d4h, se)

    rr1 = abs(tp1 - entry) / sl_dist if sl_dist > 0 else 0

    if rr1 < se["min_rr"]:
        log.info("%s signal rejected — RR %.2f below minimum %.2f", coin, rr1, se["min_rr"])
        return None

    rr2 = abs(tp2 - entry) / sl_dist if tp2 and sl_dist > 0 else None

    grade = _assign_grade(bias, context)

    narrative = _build_narrative(
        coin      = coin,
        direction = direction,
        bias      = bias,
        zone      = zone,
        trigger   = trigger,
        entry     = entry,
        sl        = sl,
        tp1       = tp1,
        tp2       = tp2,
        rr1       = rr1,
        tp1_label = tp1_label,
        tp2_label = tp2_label,
        sl_pct    = sl_pct,
        context   = context
    )

    return {
        "coin":          coin,
        "direction":     direction,
        "grade":         grade,
        "score":         _grade_to_score(grade),
        "signal_type":   "FULL",
        "entry":         round(entry, 6),
        "sl":            round(sl, 6),
        "tp1":           round(tp1, 6),
        "tp2":           round(tp2, 6) if tp2 else None,
        "sl_pct":        round(sl_pct, 3),
        "actual_rr":     round(rr1, 2),
        "rr2":           round(rr2, 2) if rr2 else None,
        "tp1_label":     tp1_label,
        "tp2_label":     tp2_label,
        "zone_type":     zone["type"],
        "zone_top":      zone["top"],
        "zone_bottom":   zone["bottom"],
        "trigger":       trigger,
        "sweep_age_h":   bias.get("sweep_age_hours"),
        "sweep_label":   bias.get("sweep_label"),
        "displacement":  bias.get("displacement"),
        "bias_strength": bias.get("strength"),
        "atr_4h":        round(atr_4h, 6),
        "narrative":     narrative,
        "generated_at":  time.time(),
    }


def validate_risk(
    entry:     float,
    zone:      dict,
    direction: str,
    d4h:       dict
) -> dict:
    se      = cfg.SIGNAL_ENGINE
    is_long = direction == "LONG"
    atr_4h  = d4h.get("atr") or entry * 0.015

    sl = _calculate_sl_from_zone(
        is_long = is_long,
        entry   = entry,
        zone    = zone,
        atr_4h  = atr_4h,
        se      = se
    )

    if sl is None:
        return {"valid": False, "reason": "sl_calculation_failed"}

    sl_dist = abs(entry - sl)
    sl_pct  = sl_dist / entry * 100

    if sl_pct < 0.2:
        return {"valid": False, "reason": f"sl_too_tight_{sl_pct:.3f}pct"}
    if sl_pct > 8.0:
        return {"valid": False, "reason": f"sl_too_wide_{sl_pct:.3f}pct"}

    min_tp1 = entry + sl_dist * se["min_rr"] if is_long else entry - sl_dist * se["min_rr"]
    rr      = se["min_rr"]

    swings  = d4h.get("swings", {})
    tp1     = _nearest_structural_tp(is_long, entry, sl_dist, swings, d4h, se)
    if tp1:
        rr = abs(tp1 - entry) / sl_dist
    else:
        tp1 = min_tp1

    if rr < se["min_rr"]:
        return {"valid": False, "reason": f"rr_too_low_{rr:.2f}"}

    return {
        "valid":  True,
        "sl":     round(sl, 6),
        "tp1":    round(tp1, 6),
        "tp2":    None,
        "rr":     round(rr, 2),
        "sl_pct": round(sl_pct, 3),
    }


def _calculate_sl(
    is_long:  bool,
    entry:    float,
    zone:     dict,
    trigger:  dict,
    atr_4h:   float,
    se:       dict
) -> float | None:
    buffer = atr_4h * se["sl_buffer_atr_mult"]

    candle_low  = trigger.get("candle_low")
    candle_high = trigger.get("candle_high")

    if is_long:
        if candle_low and candle_low < entry:
            sl = candle_low - buffer
            if sl < entry:
                return sl
        sl = zone["bottom"] - buffer
        if sl < entry:
            return sl
    else:
        if candle_high and candle_high > entry:
            sl = candle_high + buffer
            if sl > entry:
                return sl
        sl = zone["top"] + buffer
        if sl > entry:
            return sl

    return None


def _calculate_sl_from_zone(
    is_long:  bool,
    entry:    float,
    zone:     dict,
    atr_4h:   float,
    se:       dict
) -> float | None:
    buffer = atr_4h * se["sl_buffer_atr_mult"]

    if is_long:
        sl = zone["bottom"] - buffer
        if sl < entry:
            return sl
    else:
        sl = zone["top"] + buffer
        if sl > entry:
            return sl

    return None


def _calculate_tp1(
    is_long:  bool,
    entry:    float,
    sl_dist:  float,
    d1h:      dict,
    d4h:      dict,
    se:       dict
) -> tuple[float, str]:
    swings_1h = d1h.get("swings", {})
    tp        = _nearest_structural_tp(is_long, entry, sl_dist, swings_1h, d1h, se)

    if tp:
        return tp, "1H structural level"

    swings_4h = d4h.get("swings", {})
    tp        = _nearest_structural_tp(is_long, entry, sl_dist, swings_4h, d4h, se)

    if tp:
        return tp, "4H structural level"

    fallback = (
        entry + sl_dist * se["min_rr"]
        if is_long
        else entry - sl_dist * se["min_rr"]
    )
    return fallback, f"{se['min_rr']}R floor"


def _calculate_tp2(
    is_long:  bool,
    entry:    float,
    sl_dist:  float,
    d4h:      dict,
    se:       dict
) -> tuple[float | None, str]:
    swings = d4h.get("swings", {})

    if is_long:
        highs = swings.get("highs", [])
        candidates = [
            h["price"] for h in highs
            if h["price"] > entry and
            abs(h["price"] - entry) / sl_dist >= se["min_rr"] * 1.5
        ]
        if candidates:
            tp = min(candidates)
            return tp, "4H swing high"
    else:
        lows = swings.get("lows", [])
        candidates = [
            l["price"] for l in lows
            if l["price"] < entry and
            abs(l["price"] - entry) / sl_dist >= se["min_rr"] * 1.5
        ]
        if candidates:
            tp = max(candidates)
            return tp, "4H swing low"

    poc = d4h.get("poc")
    if poc:
        if is_long and poc > entry:
            rr = abs(poc - entry) / sl_dist
            if rr >= se["min_rr"] * 1.5:
                return poc, "4H POC"
        if not is_long and poc < entry:
            rr = abs(poc - entry) / sl_dist
            if rr >= se["min_rr"] * 1.5:
                return poc, "4H POC"

    return None, ""


def _nearest_structural_tp(
    is_long:  bool,
    entry:    float,
    sl_dist:  float,
    swings:   dict,
    data:     dict,
    se:       dict
) -> float | None:
    candidates = []

    if is_long:
        for h in swings.get("highs", []):
            price = h["price"]
            if price <= entry:
                continue
            rr = abs(price - entry) / sl_dist
            if rr >= se["min_rr"]:
                candidates.append(price)

        fvgs = data.get("fvgs", [])
        for fvg in fvgs:
            if fvg.get("type") == "bear" and fvg.get("bottom", 0) > entry:
                rr = abs(fvg["bottom"] - entry) / sl_dist
                if rr >= se["min_rr"]:
                    candidates.append(fvg["bottom"])

        obs = data.get("order_blocks", {})
        nb  = obs.get("nearest_bear")
        if nb and not nb.get("mitigated") and nb.get("bottom", 0) > entry:
            rr = abs(nb["bottom"] - entry) / sl_dist
            if rr >= se["min_rr"]:
                candidates.append(nb["bottom"])

        return min(candidates) if candidates else None

    else:
        for l in swings.get("lows", []):
            price = l["price"]
            if price >= entry:
                continue
            rr = abs(price - entry) / sl_dist
            if rr >= se["min_rr"]:
                candidates.append(price)

        fvgs = data.get("fvgs", [])
        for fvg in fvgs:
            if fvg.get("type") == "bull" and fvg.get("top", 0) < entry:
                rr = abs(fvg["top"] - entry) / sl_dist
                if rr >= se["min_rr"]:
                    candidates.append(fvg["top"])

        obs = data.get("order_blocks", {})
        nb  = obs.get("nearest_bull")
        if nb and not nb.get("mitigated") and nb.get("top", 0) < entry:
            rr = abs(nb["top"] - entry) / sl_dist
            if rr >= se["min_rr"]:
                candidates.append(nb["top"])

        return max(candidates) if candidates else None


def _assign_grade(bias: dict, context: dict) -> str:
    strength     = bias.get("strength", "weak")
    sweep_age    = bias.get("sweep_age_hours", 999)
    disp_strong  = bias.get("displacement_strong", False)
    disp_confirm = bias.get("displacement", False)
    se           = cfg.SIGNAL_ENGINE

    if (
        strength == "strong" and
        sweep_age <= se["sweep_max_age_hours"] / 2 and
        disp_strong
    ):
        return "A+"

    if (
        strength in ("strong", "moderate") and
        sweep_age <= se["sweep_max_age_hours"] and
        disp_confirm
    ):
        return "A"

    return "B"


def _grade_to_score(grade: str) -> float:
    return {"A+": 95.0, "A": 80.0, "B": 60.0}.get(grade, 60.0)


def _build_narrative(
    coin:      str,
    direction: str,
    bias:      dict,
    zone:      dict,
    trigger:   str,
    entry:     float,
    sl:        float,
    tp1:       float,
    tp2:       float | None,
    rr1:       float,
    tp1_label: str,
    tp2_label: str,
    sl_pct:    float,
    context:   dict
) -> str:
    sweep_age = bias.get("sweep_age_hours", 0)
    sweep_lbl = bias.get("sweep_label", "key level")
    sweep_lvl = bias.get("sweep_level", 0)
    disp_atr  = bias.get("displacement_atr", 0)
    zone_type = zone["type"]
    z_bottom  = zone["bottom"]
    z_top     = zone["top"]
    touches   = zone.get("touch_count", 0)

    lines = [
        f"{coin} {direction} — {_assign_grade(bias, context)}",
        "",
        f"{sweep_lbl} swept {sweep_age:.1f}h ago at {sweep_lvl:.4f}",
    ]

    if bias.get("displacement"):
        lines.append(
            f"{disp_atr:.1f}x ATR displacement confirmed institutional intent"
        )

    lines += [
        f"{zone_type} zone {z_bottom:.4f}-{z_top:.4f} — "
        f"{'unmitigated' if touches == 0 else f'touched {touches}x'}",
        f"15M {trigger} confirmed rejection",
        "",
        f"Entry:  {entry:.4f}",
        f"SL:     {sl:.4f}  ({sl_pct:.2f}%)",
        f"TP1:    {tp1:.4f}  ({rr1:.1f}R — {tp1_label})",
    ]

    if tp2:
        lines.append(f"TP2:    {tp2:.4f}  ({tp2_label})")

    lines += [
        "",
        f"Thesis invalid if 15M closes beyond {sl:.4f}",
    ]

    return "\n".join(lines)