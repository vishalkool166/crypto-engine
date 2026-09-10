import logging
from dataclasses import dataclass
from typing import Optional
from config import cfg, get_coin_config

log = logging.getLogger(__name__)

HE = cfg.HYBRID_ENGINE


@dataclass
class RiskResult:
    valid:     bool
    entry:     float
    sl:        float
    tp1:       float
    tp2:       Optional[float]
    sl_pct:    float
    sl_dist:   float
    rr1:       float
    rr2:       Optional[float]
    tp1_label: str
    tp2_label: str
    sl_reason: str
    reason:    str


def calculate(
    direction:   str,
    entry:       float,
    swing_level: float,
    atr:         float,
    coin:        str = "",
    rr1:         float = None,
    rr2:         float = None,
) -> RiskResult:
    is_long = direction == "LONG"
    buffer  = atr * 0.5

    coin_cfg = get_coin_config(coin) if coin else {}
    tp_mult  = coin_cfg.get("tp", 2.5)

    if rr1 is None:
        rr1 = tp_mult
    if rr2 is None:
        rr2 = tp_mult * 1.5

    if is_long:
        sl        = round(swing_level - buffer, 6)
        sl_reason = f"below_swing_low:{swing_level:.4f}"
    else:
        sl        = round(swing_level + buffer, 6)
        sl_reason = f"above_swing_high:{swing_level:.4f}"

    if is_long and sl >= entry:
        return _invalid("sl_above_entry")
    if not is_long and sl <= entry:
        return _invalid("sl_below_entry")

    sl_dist = abs(entry - sl)
    sl_pct  = sl_dist / entry * 100

    if sl_pct < HE.get("sl_min_pct", 0.3):
        return _invalid(f"sl_too_tight:{sl_pct:.3f}")
    if sl_pct > HE.get("sl_max_pct", 5.0):
        return _invalid(f"sl_too_wide:{sl_pct:.3f}")

    if is_long:
        tp1 = round(entry + sl_dist * rr1, 6)
        tp2 = round(entry + sl_dist * rr2, 6)
    else:
        tp1 = round(entry - sl_dist * rr1, 6)
        tp2 = round(entry - sl_dist * rr2, 6)

    actual_rr1 = abs(tp1 - entry) / sl_dist if sl_dist > 0 else 0.0

    min_rr = coin_cfg.get("tp", HE.get("tp1_min_rr", 1.5))
    if actual_rr1 < min_rr * 0.9:
        return _invalid(f"rr_too_low:{actual_rr1:.2f}")

    return RiskResult(
        valid     = True,
        entry     = round(entry, 6),
        sl        = sl,
        tp1       = tp1,
        tp2       = tp2,
        sl_pct    = round(sl_pct, 3),
        sl_dist   = round(sl_dist, 6),
        rr1       = round(actual_rr1, 2),
        rr2       = round(abs(tp2 - entry) / sl_dist, 2) if sl_dist > 0 else None,
        tp1_label = f"{rr1:.1f}R target",
        tp2_label = f"{rr2:.1f}R target",
        sl_reason = sl_reason,
        reason    = "",
    )


def _invalid(reason: str) -> RiskResult:
    return RiskResult(
        valid     = False,
        entry     = 0.0,
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
        reason    = reason,
    )