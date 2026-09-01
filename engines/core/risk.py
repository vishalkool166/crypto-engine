from dataclasses import dataclass
from typing import Optional


@dataclass
class RiskResult:
    valid:    bool
    entry:    float
    sl:       float
    tp1:      float
    tp2:      float
    sl_pct:   float
    sl_dist:  float
    rr1:      float
    rr2:      float
    reason:   str


def calculate_risk(
    direction:   str,
    entry:       float,
    swing_level: float,
    atr:         float,
    rr1:         float = 2.5,
    rr2:         float = 4.0,
) -> RiskResult:
    is_long = direction == "LONG"
    buffer  = atr * 0.5

    if is_long:
        if swing_level >= entry:
            return _invalid("swing_low_above_entry")
        sl        = round(swing_level - buffer, 6)
    else:
        if swing_level <= entry:
            return _invalid("swing_high_below_entry")
        sl        = round(swing_level + buffer, 6)

    if is_long and sl >= entry:
        return _invalid("sl_above_entry")
    if not is_long and sl <= entry:
        return _invalid("sl_below_entry")

    sl_dist = abs(entry - sl)
    sl_pct  = sl_dist / entry * 100

    if sl_pct < 0.3:
        return _invalid(f"sl_too_tight:{sl_pct:.3f}")
    if sl_pct > 5.0:
        return _invalid(f"sl_too_wide:{sl_pct:.3f}")

    if is_long:
        tp1 = entry + sl_dist * rr1
        tp2 = entry + sl_dist * rr2
    else:
        tp1 = entry - sl_dist * rr1
        tp2 = entry - sl_dist * rr2

    return RiskResult(
        valid   = True,
        entry   = round(entry, 6),
        sl      = round(sl,    6),
        tp1     = round(tp1,   6),
        tp2     = round(tp2,   6),
        sl_pct  = round(sl_pct, 3),
        sl_dist = round(sl_dist, 6),
        rr1     = rr1,
        rr2     = rr2,
        reason  = "",
    )


def _invalid(reason: str) -> RiskResult:
    return RiskResult(
        valid   = False,
        entry   = 0.0,
        sl      = 0.0,
        tp1     = 0.0,
        tp2     = 0.0,
        sl_pct  = 0.0,
        sl_dist = 0.0,
        rr1     = 0.0,
        rr2     = 0.0,
        reason  = reason,
    )