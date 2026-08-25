import logging
from dataclasses import dataclass
from typing import Optional
from config import cfg

log = logging.getLogger(__name__)

HE = cfg.HYBRID_ENGINE


@dataclass
class RiskResult:
    valid:      bool
    sl:         float
    tp1:        float
    tp2:        Optional[float]
    sl_pct:     float
    sl_dist:    float
    rr1:        float
    rr2:        Optional[float]
    tp1_label:  str
    tp2_label:  str
    sl_reason:  str
    entry:      float
    reason:     str


def calculate(
    direction: str,
    entry:     float,
    sweep:     object,
    zone:      object,
    ict:       object,
    atr_15m:   float,
    d1h:       dict,
    d4h:       dict,
) -> RiskResult:
    is_long = direction == "LONG"

    sl, sl_reason = _calculate_sl(
        is_long  = is_long,
        entry    = entry,
        sweep    = sweep,
        zone     = zone,
        ict      = ict,
        atr_15m  = atr_15m,
    )

    if sl is None:
        return _invalid("sl_calculation_failed")

    if is_long and sl >= entry:
        return _invalid("sl_above_entry")
    if not is_long and sl <= entry:
        return _invalid("sl_below_entry")

    sl_dist = abs(entry - sl)
    sl_pct  = sl_dist / entry * 100

    if sl_pct < HE["sl_min_pct"]:
        zone_sl = _zone_fallback_sl(is_long, zone, atr_15m)
        if zone_sl is not None:
            zone_sl_dist = abs(entry - zone_sl)
            zone_sl_pct  = zone_sl_dist / entry * 100
            if HE["sl_min_pct"] <= zone_sl_pct <= HE["sl_max_pct"]:
                sl       = zone_sl
                sl_dist  = zone_sl_dist
                sl_pct   = zone_sl_pct
                sl_reason= "zone_fallback_sl"
            else:
                return _invalid(f"sl_too_tight:{sl_pct:.3f}pct")
        else:
            return _invalid(f"sl_too_tight:{sl_pct:.3f}pct")

    if sl_pct > HE["sl_max_pct"]:
        return _invalid(f"sl_too_wide:{sl_pct:.3f}pct")

    tp1, tp1_label = _find_tp1(is_long, entry, sl_dist, d1h, d4h)
    rr1            = abs(tp1 - entry) / sl_dist if sl_dist > 0 else 0.0

    if rr1 < HE["tp1_min_rr"]:
        return _invalid(f"rr_too_low:{rr1:.2f}")

    tp1, tp1_label = _check_poc_as_tp(is_long, entry, sl_dist, tp1, tp1_label, d4h, d1h)

    tp2, tp2_label = _find_tp2(is_long, entry, sl_dist, d4h)
    rr2            = abs(tp2 - entry) / sl_dist if tp2 and sl_dist > 0 else None

    return RiskResult(
        valid     = True,
        sl        = round(sl, 6),
        tp1       = round(tp1, 6),
        tp2       = round(tp2, 6) if tp2 else None,
        sl_pct    = round(sl_pct, 3),
        sl_dist   = round(sl_dist, 6),
        rr1       = round(rr1, 2),
        rr2       = round(rr2, 2) if rr2 else None,
        tp1_label = tp1_label,
        tp2_label = tp2_label,
        sl_reason = sl_reason,
        entry     = round(entry, 6),
        reason    = "",
    )


def _calculate_sl(
    is_long:  bool,
    entry:    float,
    sweep:    object,
    zone:     object,
    ict:      object,
    atr_15m:  float,
) -> tuple[Optional[float], str]:
    buffer = atr_15m * HE["sl_buffer_atr_mult"]

    if sweep is not None:
        if is_long and sweep.sweep_low:
            return round(float(sweep.sweep_low) - buffer, 6), f"below_sweep_wick:{sweep.sweep_low:.4f}"
        if not is_long and sweep.sweep_high:
            return round(float(sweep.sweep_high) + buffer, 6), f"above_sweep_wick:{sweep.sweep_high:.4f}"

    if ict is not None:
        if is_long and ict.candle_low:
            return round(float(ict.candle_low) - buffer, 6), "below_trigger_candle_low"
        if not is_long and ict.candle_high:
            return round(float(ict.candle_high) + buffer, 6), "above_trigger_candle_high"

    if zone is not None:
        return _zone_fallback_sl(is_long, zone, atr_15m), "zone_boundary_sl"

    return None, ""


def _zone_fallback_sl(
    is_long: bool,
    zone:    object,
    atr_15m: float,
) -> Optional[float]:
    if zone is None:
        return None
    buffer = atr_15m * HE["sl_buffer_atr_mult"]
    if is_long:
        return round(float(zone.bottom) - buffer, 6)
    return round(float(zone.top) + buffer, 6)


def _find_tp1(
    is_long:  bool,
    entry:    float,
    sl_dist:  float,
    d1h:      dict,
    d4h:      dict,
) -> tuple[float, str]:
    candidates = []
    min_rr     = HE["tp1_min_rr"]

    swings_1h = d1h.get("swings", {})
    if is_long:
        for h in swings_1h.get("highs", []):
            p = float(h["price"])
            if p > entry and (p - entry) / sl_dist >= min_rr:
                candidates.append((p, "1H swing high", 1))
        for fvg in d1h.get("fvgs", []):
            if fvg.get("type") == "bear":
                p = float(fvg.get("bottom", 0))
                if p > entry and (p - entry) / sl_dist >= min_rr:
                    candidates.append((p, "1H bearish FVG", 1))
        ob = d1h.get("order_blocks", {}).get("nearest_bear")
        if ob and not ob.get("mitigated"):
            p = float(ob.get("bottom", 0))
            if p > entry and (p - entry) / sl_dist >= min_rr:
                candidates.append((p, "1H bear OB", 1))
    else:
        for l in swings_1h.get("lows", []):
            p = float(l["price"])
            if p < entry and (entry - p) / sl_dist >= min_rr:
                candidates.append((p, "1H swing low", 1))
        for fvg in d1h.get("fvgs", []):
            if fvg.get("type") == "bull":
                p = float(fvg.get("top", 0))
                if p < entry and (entry - p) / sl_dist >= min_rr:
                    candidates.append((p, "1H bullish FVG", 1))
        ob = d1h.get("order_blocks", {}).get("nearest_bull")
        if ob and not ob.get("mitigated"):
            p = float(ob.get("top", 0))
            if p < entry and (entry - p) / sl_dist >= min_rr:
                candidates.append((p, "1H bull OB", 1))

    swings_4h = d4h.get("swings", {})
    if is_long:
        for h in swings_4h.get("highs", []):
            p = float(h["price"])
            if p > entry and (p - entry) / sl_dist >= min_rr:
                candidates.append((p, "4H swing high", 2))
        ob = d4h.get("order_blocks", {}).get("nearest_bear")
        if ob and not ob.get("mitigated"):
            p = float(ob.get("bottom", 0))
            if p > entry and (p - entry) / sl_dist >= min_rr:
                candidates.append((p, "4H bear OB", 2))
    else:
        for l in swings_4h.get("lows", []):
            p = float(l["price"])
            if p < entry and (entry - p) / sl_dist >= min_rr:
                candidates.append((p, "4H swing low", 2))
        ob = d4h.get("order_blocks", {}).get("nearest_bull")
        if ob and not ob.get("mitigated"):
            p = float(ob.get("top", 0))
            if p < entry and (entry - p) / sl_dist >= min_rr:
                candidates.append((p, "4H bull OB", 2))

    if not candidates:
        tp    = entry + sl_dist * min_rr if is_long else entry - sl_dist * min_rr
        return round(tp, 6), f"{min_rr}R_floor"

    candidates.sort(key=lambda x: (x[2], x[0] if is_long else -x[0]))
    tp, label, _ = candidates[0]
    return round(tp, 6), label


def _check_poc_as_tp(
    is_long:   bool,
    entry:     float,
    sl_dist:   float,
    tp1:       float,
    tp1_label: str,
    d4h:       dict,
    d1h:       dict,
) -> tuple[float, str]:
    min_rr = 1.2

    for poc, label in [
        (d1h.get("poc"), "1H POC"),
        (d4h.get("poc"), "4H POC"),
    ]:
        if not poc:
            continue
        poc = float(poc)
        if is_long:
            between = entry < poc < tp1
            rr      = (poc - entry) / sl_dist if sl_dist > 0 else 0
        else:
            between = tp1 < poc < entry
            rr      = (entry - poc) / sl_dist if sl_dist > 0 else 0

        if between and rr >= min_rr:
            return round(poc, 6), f"{label} (intermediate)"

    return tp1, tp1_label


def _find_tp2(
    is_long:  bool,
    entry:    float,
    sl_dist:  float,
    d4h:      dict,
) -> tuple[Optional[float], str]:
    candidates = []
    min_rr     = HE["tp2_min_rr"]

    swings = d4h.get("swings", {})
    if is_long:
        for h in swings.get("highs", []):
            p = float(h["price"])
            if p > entry and (p - entry) / sl_dist >= min_rr:
                candidates.append((p, "4H swing high"))
        poc = d4h.get("poc")
        if poc and float(poc) > entry and (float(poc) - entry) / sl_dist >= min_rr:
            candidates.append((float(poc), "4H POC"))
        vah = d4h.get("vah")
        if vah and float(vah) > entry and (float(vah) - entry) / sl_dist >= min_rr:
            candidates.append((float(vah), "4H VAH"))
    else:
        for l in swings.get("lows", []):
            p = float(l["price"])
            if p < entry and (entry - p) / sl_dist >= min_rr:
                candidates.append((p, "4H swing low"))
        poc = d4h.get("poc")
        if poc and float(poc) < entry and (entry - float(poc)) / sl_dist >= min_rr:
            candidates.append((float(poc), "4H POC"))
        val = d4h.get("val")
        if val and float(val) < entry and (entry - float(val)) / sl_dist >= min_rr:
            candidates.append((float(val), "4H VAL"))

    if not candidates:
        return None, ""

    candidates.sort(key=lambda x: x[0] if is_long else -x[0])
    tp, label = candidates[0]
    return round(tp, 6), label


def _invalid(reason: str) -> RiskResult:
    return RiskResult(
        valid     = False,
        sl        = 0.0,
        tp1       = 0.0,
        tp2       = None,
        sl_pct    = 0.0,
        sl_dist   = 0.0,
        rr1       = 0.0,
        rr2       = None,
        tp1_label = "",
        tp2_label = "",
        sl_reason = "",
        entry     = 0.0,
        reason    = reason,
    )