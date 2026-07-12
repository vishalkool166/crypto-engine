import logging
from config import cfg

log = logging.getLogger(__name__)

SE = cfg.SCALP_ENGINE


def _find_tp1(
    is_long:  bool,
    entry:    float,
    sl_dist:  float,
    d1h:      dict,
    d4h:      dict,
) -> tuple[float, str]:

    candidates = []
    min_rr     = SE["tp1_min_rr"]

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
        return round(tp, 6), f"{min_rr}R floor"

    candidates.sort(key=lambda x: (x[2], x[0] if is_long else -x[0]))
    tp, label, _ = candidates[0]
    return round(tp, 6), label


def _check_poc_as_tp(
    is_long:  bool,
    entry:    float,
    sl_dist:  float,
    tp1:      float,
    d4h:      dict,
    d1h:      dict,
    min_rr:   float = 1.2,
) -> tuple[float, str, bool]:
    poc_4h = d4h.get("poc")
    poc_1h = d1h.get("poc")

    best_poc       = None
    best_poc_label = ""

    for poc, label in [(poc_1h, "1H POC"), (poc_4h, "4H POC")]:
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
            if best_poc is None:
                best_poc       = poc
                best_poc_label = label
            else:
                if is_long and poc > best_poc:
                    best_poc       = poc
                    best_poc_label = label
                elif not is_long and poc < best_poc:
                    best_poc       = poc
                    best_poc_label = label

    if best_poc is not None:
        return round(best_poc, 6), best_poc_label, True

    return tp1, "", False


def _find_tp2(
    is_long:  bool,
    entry:    float,
    sl_dist:  float,
    d4h:      dict,
) -> tuple[float | None, str]:

    candidates = []
    min_rr     = SE["tp2_min_rr"]

    swings = d4h.get("swings", {})
    if is_long:
        for h in swings.get("highs", []):
            p = float(h["price"])
            if p > entry and (p - entry) / sl_dist >= min_rr:
                candidates.append((p, "4H swing high"))
        poc = d4h.get("poc")
        if poc and poc > entry and (poc - entry) / sl_dist >= min_rr:
            candidates.append((float(poc), "4H POC"))
        vah = d4h.get("vah")
        if vah and vah > entry and (vah - entry) / sl_dist >= min_rr:
            candidates.append((float(vah), "4H VAH"))
    else:
        for l in swings.get("lows", []):
            p = float(l["price"])
            if p < entry and (entry - p) / sl_dist >= min_rr:
                candidates.append((p, "4H swing low"))
        poc = d4h.get("poc")
        if poc and poc < entry and (entry - poc) / sl_dist >= min_rr:
            candidates.append((float(poc), "4H POC"))
        val = d4h.get("val")
        if val and val < entry and (entry - val) / sl_dist >= min_rr:
            candidates.append((float(val), "4H VAL"))

    if not candidates:
        return None, ""

    candidates.sort(key=lambda x: x[0] if is_long else -x[0])
    tp, label = candidates[0]
    return round(tp, 6), label


def calculate(
    direction: str,
    entry:     float,
    sweep:     dict,
    zone:      dict,
    trigger:   dict,
    atr_15m:   float,
    d1h:       dict,
    d4h:       dict,
) -> dict:

    is_long = direction == "LONG"

    if is_long:
        sweep_extreme = sweep.get("sweep_low")
        if sweep_extreme:
            sl = float(sweep_extreme) - atr_15m * SE["sl_buffer_atr_mult"]
        else:
            candle_low = trigger.get("candle_low", zone["bottom"])
            sl = float(candle_low) - atr_15m * SE["sl_buffer_atr_mult"]
    else:
        sweep_extreme = sweep.get("sweep_high")
        if sweep_extreme:
            sl = float(sweep_extreme) + atr_15m * SE["sl_buffer_atr_mult"]
        else:
            candle_high = trigger.get("candle_high", zone["top"])
            sl = float(candle_high) + atr_15m * SE["sl_buffer_atr_mult"]

    sl = round(sl, 6)

    if is_long and sl >= entry:
        return {"valid": False, "reason": "sl_above_entry"}
    if not is_long and sl <= entry:
        return {"valid": False, "reason": "sl_below_entry"}

    sl_dist = abs(entry - sl)
    sl_pct  = sl_dist / entry * 100

    if sl_pct < SE["sl_min_pct"]:
        if is_long:
            zone_sl = float(zone.get("bottom", 0)) - atr_15m * SE["sl_buffer_atr_mult"]
        else:
            zone_sl = float(zone.get("top", 0)) + atr_15m * SE["sl_buffer_atr_mult"]

        zone_sl      = round(zone_sl, 6)
        zone_sl_dist = abs(entry - zone_sl)
        zone_sl_pct  = zone_sl_dist / entry * 100

        if zone_sl_pct >= SE["sl_min_pct"] and zone_sl_pct <= SE["sl_max_pct"]:
            sl      = zone_sl
            sl_dist = zone_sl_dist
            sl_pct  = zone_sl_pct
            log.info(
                "SL fallback to zone: entry=%.6f zone_sl=%.6f sl_pct=%.3f%%",
                entry, sl, sl_pct
            )
        else:
            return {"valid": False, "reason": f"sl_too_tight_{sl_pct:.3f}pct"}

    if sl_pct > SE["sl_max_pct"]:
        return {"valid": False, "reason": f"sl_too_wide_{sl_pct:.3f}pct"}

    tp1_raw, tp1_label = _find_tp1(is_long, entry, sl_dist, d1h, d4h)

    tp1, poc_label, poc_used = _check_poc_as_tp(
        is_long   = is_long,
        entry     = entry,
        sl_dist   = sl_dist,
        tp1       = tp1_raw,
        d4h       = d4h,
        d1h       = d1h,
        min_rr    = 1.2,
    )

    if poc_used:
        tp2, tp2_label = tp1_raw, tp1_label
        tp1_label      = poc_label + " (POC)"
        log.info(
            "POC used as TP1: entry=%.6f poc=%.6f original_tp1=%.6f",
            entry, tp1, tp2
        )
    else:
        tp2, tp2_label = _find_tp2(is_long, entry, sl_dist, d4h)

    rr1 = abs(tp1 - entry) / sl_dist
    rr2 = abs(tp2 - entry) / sl_dist if tp2 else None

    if rr1 < SE["tp1_min_rr"]:
        return {"valid": False, "reason": f"rr_too_low_{rr1:.2f}"}

    return {
        "valid":      True,
        "sl":         sl,
        "tp1":        tp1,
        "tp2":        tp2,
        "sl_pct":     round(sl_pct, 3),
        "sl_dist":    round(sl_dist, 6),
        "rr1":        round(rr1, 2),
        "rr2":        round(rr2, 2) if rr2 else None,
        "tp1_label":  tp1_label,
        "tp2_label":  tp2_label,
        "sl_reason":  (
            f"Below sweep wick {sweep_extreme:.4f}"
            if sweep_extreme
            else "Below candle low / zone fallback"
        ),
        "poc_used":   poc_used,
    }