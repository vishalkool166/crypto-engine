import time
import logging
from pandas import DataFrame
from engines.sweep import detect_sweep
from engines.displacement import detect_displacement
from config import cfg

log = logging.getLogger(__name__)

_SWEEP_MAX_AGE_HOURS = 48
_SLOPE_FLAT_THRESHOLD = 0.10


def get_htf_bias(
    d1w:        dict,
    d1d:        dict,
    df_1d:      DataFrame,
    key_levels: dict
) -> dict:
    se = cfg.SIGNAL_ENGINE

    direction = _get_direction(d1w, d1d)
    if direction == "NONE":
        return _no_bias("trend_undefined")

    slope_ok = _slope_defined(d1d, se["slope_flat_threshold"])
    if not slope_ok:
        return _no_bias("slope_flat")

    atr    = d1d.get("atr") or float(df_1d["close"].iloc[-1]) * 0.015
    swings = d1d.get("swings", {})

    sweep = detect_sweep(
        df        = df_1d,
        key_levels= key_levels,
        atr       = atr,
        swings    = swings,
        timeframe = "1d"
    )

    if not sweep.get("detected"):
        return _no_bias("no_sweep")

    sweep_age = sweep.get("age_hours", 999)
    if sweep_age > se["sweep_max_age_hours"]:
        return _no_bias("sweep_expired")

    disp = detect_displacement(df_1d.tail(10), atr)

    strength = _grade_strength(sweep, disp, d1w, d1d, direction, se)

    return {
        "valid":                True,
        "direction":            direction,
        "slope_defined":        True,
        "sweep_detected":       True,
        "sweep_age_hours":      round(sweep_age, 1),
        "sweep_label":          sweep.get("label", ""),
        "sweep_level":          sweep.get("level", 0),
        "sweep_score":          sweep.get("score", 0),
        "sweep_low":            sweep.get("sweep_low"),
        "sweep_high":           sweep.get("sweep_high"),
        "sweep_type":           sweep.get("type", ""),
        "displacement":         disp.get("confirmed", False),
        "displacement_strong":  not disp.get("moderate", True),
        "displacement_atr":     disp.get("range_mult", 0),
        "atr":                  round(atr, 6),
        "strength":             strength,
        "no_bias_reason":       None,
        "evaluated_at":         time.time(),
    }


def _get_direction(d1w: dict, d1d: dict) -> str:
    d1_cls = d1d.get("trend", {}).get("cls", "neutral")
    wk_cls = d1w.get("trend", {}).get("cls", "neutral")

    if d1_cls == "bull":
        return "LONG"
    if d1_cls == "bear":
        return "SHORT"
    if wk_cls == "bull" and d1_cls != "bear":
        return "LONG"
    if wk_cls == "bear" and d1_cls != "bull":
        return "SHORT"
    return "NONE"


def _slope_defined(d1d: dict, threshold: float) -> bool:
    s50 = d1d.get("slope50")
    s20 = d1d.get("slope20")
    if s50 is None:
        return False
    if abs(s50) < threshold:
        return False
    if s20 is not None and abs(s20) < threshold:
        return False
    return True


def _grade_strength(
    sweep:     dict,
    disp:      dict,
    d1w:       dict,
    d1d:       dict,
    direction: str,
    se:        dict
) -> str:
    score = 0

    sweep_age = sweep.get("age_hours", 999)
    if sweep_age <= se["sweep_max_age_hours"] / 2:
        score += 2
    else:
        score += 1

    if sweep.get("score", 0) >= se["sweep_strong_score"]:
        score += 2
    elif sweep.get("score", 0) >= se["sweep_moderate_score"]:
        score += 1

    if disp.get("confirmed"):
        if disp.get("range_mult", 0) >= se["displacement_strong_atr"]:
            score += 2
        else:
            score += 1

    wk_cls = d1w.get("trend", {}).get("cls", "neutral")
    d1_cls = d1d.get("trend", {}).get("cls", "neutral")
    if (direction == "LONG"  and wk_cls == "bull" and d1_cls == "bull") or \
       (direction == "SHORT" and wk_cls == "bear" and d1_cls == "bear"):
        score += 2

    struct = d1d.get("structure", {}).get("struct_bias", "neutral")
    if (direction == "LONG"  and struct == "bull") or \
       (direction == "SHORT" and struct == "bear"):
        score += 1

    if score >= 7:
        return "strong"
    if score >= 4:
        return "moderate"
    return "weak"


def _no_bias(reason: str) -> dict:
    return {
        "valid":                False,
        "direction":            "NONE",
        "slope_defined":        False,
        "sweep_detected":       False,
        "sweep_age_hours":      None,
        "sweep_label":          None,
        "sweep_level":          None,
        "sweep_score":          0,
        "sweep_low":            None,
        "sweep_high":           None,
        "sweep_type":           None,
        "displacement":         False,
        "displacement_strong":  False,
        "displacement_atr":     0,
        "atr":                  0,
        "strength":             "none",
        "no_bias_reason":       reason,
        "evaluated_at":         time.time(),
    }