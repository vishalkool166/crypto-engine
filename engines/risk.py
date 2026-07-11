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
        return {"valid": False, "reason": f"sl_too_tight_{sl_pct:.3f}pct"}
    if sl_pct > SE["sl_max_pct"]:
        return {"valid": False, "reason": f"sl_too_wide_{sl_pct:.3f}pct"}

    tp1, tp1_label = _find_tp1(is_long, entry, sl_dist, d1h, d4h)
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
        "sl_reason":  f"Below sweep wick {sweep_extreme:.4f}" if sweep_extreme else f"Below candle low",
    }