import logging
import pandas as pd
from dataclasses import dataclass
from config import cfg

log = logging.getLogger(__name__)

HE = cfg.HYBRID_ENGINE


@dataclass
class ReversionResult:
    window_open:   bool
    strength:      float
    rsi:           float
    bb_touch:      bool
    extreme:       bool
    reason:        str
    score:         float


def detect(d1h: dict, df_1h: pd.DataFrame, direction: str) -> ReversionResult:
    rsi   = float(d1h.get("rsi") or 50.0)
    bb    = d1h.get("bb") or {}
    price = float(d1h.get("price") or 0)

    is_long = direction == "LONG"

    rsi_window, rsi_extreme, rsi_reason = _check_rsi(rsi, is_long)
    bb_touch, bb_reason                 = _check_bb(price, bb, is_long)

    window_open = rsi_window or bb_touch

    if not window_open:
        return ReversionResult(
            window_open = False,
            strength    = 0.0,
            rsi         = round(rsi, 2),
            bb_touch    = bb_touch,
            extreme     = False,
            reason      = f"rsi:{rsi:.1f} no_pullback",
            score       = 0.0,
        )

    score    = _compute_score(rsi, rsi_extreme, bb_touch, is_long)
    extreme  = rsi_extreme
    reason   = rsi_reason if rsi_window else bb_reason

    return ReversionResult(
        window_open = True,
        strength    = round(score, 3),
        rsi         = round(rsi, 2),
        bb_touch    = bb_touch,
        extreme     = extreme,
        reason      = reason,
        score       = round(score, 3),
    )


def _check_rsi(rsi: float, is_long: bool) -> tuple[bool, bool, str]:
    if is_long:
        max_rsi     = HE["reversion_rsi_long_max"]
        extreme_rsi = HE["reversion_rsi_extreme_long"]

        if rsi <= extreme_rsi:
            return True, True, f"rsi_extreme_pullback:{rsi:.1f}"
        if rsi <= max_rsi:
            return True, False, f"rsi_pullback:{rsi:.1f}"
        return False, False, f"rsi_too_high:{rsi:.1f}"
    else:
        min_rsi     = HE["reversion_rsi_short_min"]
        extreme_rsi = HE["reversion_rsi_extreme_short"]

        if rsi >= extreme_rsi:
            return True, True, f"rsi_extreme_bounce:{rsi:.1f}"
        if rsi >= min_rsi:
            return True, False, f"rsi_bounce:{rsi:.1f}"
        return False, False, f"rsi_too_low:{rsi:.1f}"


def _check_bb(price: float, bb: dict, is_long: bool) -> tuple[bool, str]:
    if not HE["reversion_bb_touch"]:
        return False, "bb_check_disabled"

    if not bb or not price:
        return False, "bb_data_unavailable"

    lower = float(bb.get("lower") or 0)
    upper = float(bb.get("upper") or 0)
    mid   = float(bb.get("mid")   or 0)

    if not lower or not upper or not mid:
        return False, "bb_values_missing"

    band_width = upper - lower
    if band_width <= 0:
        return False, "bb_zero_width"

    if is_long:
        proximity = (price - lower) / band_width
        if proximity <= 0.15:
            return True, f"bb_lower_touch:{price:.4f}<={lower:.4f}"
        return False, f"bb_not_near_lower:{proximity:.2f}"
    else:
        proximity = (upper - price) / band_width
        if proximity <= 0.15:
            return True, f"bb_upper_touch:{price:.4f}>={upper:.4f}"
        return False, f"bb_not_near_upper:{proximity:.2f}"


def _compute_score(
    rsi:      float,
    extreme:  bool,
    bb_touch: bool,
    is_long:  bool,
) -> float:
    score = 0.0

    if is_long:
        max_rsi     = HE["reversion_rsi_long_max"]
        extreme_rsi = HE["reversion_rsi_extreme_long"]
        if rsi <= extreme_rsi:
            score += 0.70
        elif rsi <= max_rsi:
            rsi_range = max_rsi - extreme_rsi
            if rsi_range > 0:
                score += 0.30 + 0.40 * (1 - (rsi - extreme_rsi) / rsi_range)
            else:
                score += 0.30
    else:
        min_rsi     = HE["reversion_rsi_short_min"]
        extreme_rsi = HE["reversion_rsi_extreme_short"]
        if rsi >= extreme_rsi:
            score += 0.70
        elif rsi >= min_rsi:
            rsi_range = extreme_rsi - min_rsi
            if rsi_range > 0:
                score += 0.30 + 0.40 * (rsi - min_rsi) / rsi_range
            else:
                score += 0.30

    if bb_touch:
        score += 0.30

    return min(round(score, 3), 1.0)