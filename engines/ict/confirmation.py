import logging
import pandas as pd
from dataclasses import dataclass
from typing import Optional
from config import cfg

log = logging.getLogger(__name__)

HE = cfg.HYBRID_ENGINE


@dataclass
class TriggerData:
    confirmed:   bool
    pattern:     str
    score:       float
    entry_price: float
    candle_high: float
    candle_low:  float
    vol_mult:    float
    reason:      str


@dataclass
class ICTResult:
    confirmed:     bool
    score:         float
    sweep_score:   float
    zone_score:    float
    trigger_score: float
    entry_price:   float
    candle_high:   float
    candle_low:    float
    sweep:         object
    zone:          object
    trigger:       TriggerData
    displacement:  dict
    reason:        str
    desc:          str


def confirm(
    df_4h:     pd.DataFrame,
    d4h:       dict,
    df_1h:     pd.DataFrame,
    d1h:       dict,
    df_15m:    pd.DataFrame,
    d15m:      dict,
    direction: str,
    atr_1h:    float,
    atr_15m:   float,
) -> ICTResult:
    from engines.ict.sweep import detect as detect_sweep
    from engines.ict.zone  import detect as detect_zone
    from data.rejection_stats import record_scan

    sweep_result = detect_sweep(df_1h, d1h, direction)

    if not sweep_result.detected:
        return _rejected(
            reason        = "no_sweep",
            sweep_score   = 0.0,
            zone_score    = 0.0,
            trigger_score = 0.0,
            sweep         = None,
            zone          = None,
        )

    if sweep_result.score < HE["sweep_min_score"]:
        return _rejected(
            reason        = f"sweep_score_low:{sweep_result.score:.3f}",
            sweep_score   = sweep_result.score,
            zone_score    = 0.0,
            trigger_score = 0.0,
            sweep         = sweep_result.sweep,
            zone          = None,
        )

    if not sweep_result.displacement.get("found"):
        return _rejected(
            reason        = "no_displacement",
            sweep_score   = sweep_result.score,
            zone_score    = 0.0,
            trigger_score = 0.0,
            sweep         = sweep_result.sweep,
            zone          = None,
        )

    zone_result = detect_zone(d4h, df_4h, d1h, df_1h, direction, atr_1h)

    if not zone_result.detected:
        return _rejected(
            reason        = "no_zone",
            sweep_score   = sweep_result.score,
            zone_score    = 0.0,
            trigger_score = 0.0,
            sweep         = sweep_result.sweep,
            zone          = None,
        )

    if zone_result.score < HE["zone_min_score"]:
        return _rejected(
            reason        = f"zone_score_low:{zone_result.score:.3f}",
            sweep_score   = sweep_result.score,
            zone_score    = zone_result.score,
            trigger_score = 0.0,
            sweep         = sweep_result.sweep,
            zone          = zone_result.zone,
        )

    sweep_data = sweep_result.sweep
    age_hours  = float(sweep_data.age_hours if sweep_data else 999)
    if age_hours > HE["sweep_max_age_hours"]:
        return _rejected(
            reason        = f"sweep_too_old:{age_hours:.1f}h",
            sweep_score   = sweep_result.score,
            zone_score    = zone_result.score,
            trigger_score = 0.0,
            sweep         = sweep_result.sweep,
            zone          = zone_result.zone,
        )

    zone_data   = zone_result.zone
    touch_count = int(zone_data.touch_count if zone_data else 0)
    if touch_count > HE["zone_max_touches"]:
        return _rejected(
            reason        = f"zone_too_many_touches:{touch_count}",
            sweep_score   = sweep_result.score,
            zone_score    = zone_result.score,
            trigger_score = 0.0,
            sweep         = sweep_result.sweep,
            zone          = zone_result.zone,
        )

    trigger = _detect_trigger(df_15m, zone_data, direction, atr_15m)

    if not trigger.confirmed:
        return _rejected(
            reason        = trigger.reason or "no_trigger",
            sweep_score   = sweep_result.score,
            zone_score    = zone_result.score,
            trigger_score = trigger.score,
            sweep         = sweep_result.sweep,
            zone          = zone_result.zone,
        )

    combined = round(
        sweep_result.score   * 0.40 +
        zone_result.score    * 0.35 +
        trigger.score        * 0.25,
        3,
    )

    ict_min = HE["ict_min_score"] / 100.0
    if combined < ict_min:
        return _rejected(
            reason        = f"ict_combined_low:{combined:.3f}",
            sweep_score   = sweep_result.score,
            zone_score    = zone_result.score,
            trigger_score = trigger.score,
            sweep         = sweep_result.sweep,
            zone          = zone_result.zone,
        )

    return ICTResult(
        confirmed     = True,
        score         = combined,
        sweep_score   = sweep_result.score,
        zone_score    = zone_result.score,
        trigger_score = trigger.score,
        entry_price   = trigger.entry_price,
        candle_high   = trigger.candle_high,
        candle_low    = trigger.candle_low,
        sweep         = sweep_result.sweep,
        zone          = zone_result.zone,
        trigger       = trigger,
        displacement  = sweep_result.displacement,
        reason        = "",
        desc          = (
            f"sweep:{sweep_result.score:.2f} "
            f"zone:{zone_result.score:.2f} "
            f"trigger:{trigger.score:.2f} "
            f"combined:{combined:.2f}"
        ),
    )


def _detect_trigger(
    df_15m:    pd.DataFrame,
    zone:      object,
    direction: str,
    atr_15m:   float,
) -> TriggerData:
    if df_15m is None or len(df_15m) < HE["trigger_lookback"]:
        return TriggerData(
            confirmed   = False,
            pattern     = "",
            score       = 0.0,
            entry_price = 0.0,
            candle_high = 0.0,
            candle_low  = 0.0,
            vol_mult    = 0.0,
            reason      = "insufficient_15m_data",
        )

    price = float(df_15m["close"].iloc[-1])

    zone_top    = float(zone.top)
    zone_bottom = float(zone.bottom)
    buffer      = atr_15m * 0.5

    near = (zone_bottom - buffer) <= price <= (zone_top + buffer)
    if not near:
        return TriggerData(
            confirmed   = False,
            pattern     = "",
            score       = 0.0,
            entry_price = 0.0,
            candle_high = 0.0,
            candle_low  = 0.0,
            vol_mult    = 0.0,
            reason      = "price_outside_zone",
        )

    retest_ok = _check_retest(df_15m, zone_top, zone_bottom, direction)
    if not retest_ok:
        return TriggerData(
            confirmed   = False,
            pattern     = "",
            score       = 0.0,
            entry_price = 0.0,
            candle_high = 0.0,
            candle_low  = 0.0,
            vol_mult    = 0.0,
            reason      = "retest_not_confirmed",
        )

    recent   = df_15m.tail(HE["trigger_lookback"])
    vol_mult = _vol_score(df_15m)

    engulf = _check_engulfing(recent, direction, zone_top, zone_bottom)
    if engulf:
        score = round(engulf["pattern_score"] * vol_mult, 3)
        if score >= HE["trigger_min_score"]:
            return TriggerData(
                confirmed   = True,
                pattern     = "engulfing",
                score       = score,
                entry_price = engulf["entry_price"],
                candle_high = engulf["candle_high"],
                candle_low  = engulf["candle_low"],
                vol_mult    = vol_mult,
                reason      = "",
            )

    pin = _check_pin_bar(recent, direction, zone_top, zone_bottom)
    if pin:
        score = round(pin["pattern_score"] * vol_mult, 3)
        if score >= HE["trigger_min_score"]:
            return TriggerData(
                confirmed   = True,
                pattern     = "pin_bar",
                score       = score,
                entry_price = pin["entry_price"],
                candle_high = pin["candle_high"],
                candle_low  = pin["candle_low"],
                vol_mult    = vol_mult,
                reason      = "",
            )

    return TriggerData(
        confirmed   = False,
        pattern     = "",
        score       = 0.0,
        entry_price = 0.0,
        candle_high = 0.0,
        candle_low  = 0.0,
        vol_mult    = vol_mult,
        reason      = "no_pattern",
    )


def _check_retest(
    df:         pd.DataFrame,
    zone_top:   float,
    zone_bottom:float,
    direction:  str,
) -> bool:
    if len(df) < 3:
        return False

    is_long = direction == "LONG"
    recent  = df.tail(6)

    for _, c in recent.iterrows():
        c_low   = float(c["low"])
        c_high  = float(c["high"])
        c_open  = float(c["open"])
        c_close = float(c["close"])

        if c_low <= zone_top and c_high >= zone_bottom:
            if is_long and c_close > c_open:
                return True
            if not is_long and c_close < c_open:
                return True

    return False


def _vol_score(df: pd.DataFrame) -> float:
    vol_ma  = float(df["volume"].rolling(50).mean().iloc[-1]) or 1.0
    cur_vol = float(df["volume"].iloc[-1])
    ratio   = cur_vol / vol_ma
    if ratio >= 1.5:
        return 1.2
    if ratio >= 1.1:
        return 1.0
    if ratio >= 0.8:
        return 0.85
    return 0.7


def _check_engulfing(
    df:          pd.DataFrame,
    direction:   str,
    zone_top:    float,
    zone_bottom: float,
) -> Optional[dict]:
    if len(df) < 2:
        return None

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    c_o = float(curr["open"])
    c_c = float(curr["close"])
    c_h = float(curr["high"])
    c_l = float(curr["low"])
    p_o = float(prev["open"])
    p_c = float(prev["close"])

    c_body  = abs(c_c - c_o)
    c_range = c_h - c_l

    if c_range == 0:
        return None
    if c_body / c_range < HE["trigger_min_body_ratio"]:
        return None

    touching = c_l <= zone_top and c_h >= zone_bottom
    if not touching:
        return None

    if direction == "LONG":
        if not (p_c < p_o and c_c > c_o):
            return None
        if not (c_c > p_o and c_o < p_c):
            return None
        if c_c < zone_bottom:
            return None
    else:
        if not (p_c > p_o and c_c < c_o):
            return None
        if not (c_c < p_o and c_o > p_c):
            return None
        if c_c > zone_top:
            return None

    return {
        "pattern_score": 1.0,
        "entry_price":   round(c_c, 6),
        "candle_high":   round(c_h, 6),
        "candle_low":    round(c_l, 6),
    }


def _check_pin_bar(
    df:          pd.DataFrame,
    direction:   str,
    zone_top:    float,
    zone_bottom: float,
) -> Optional[dict]:
    if len(df) < 1:
        return None

    curr = df.iloc[-1]
    c_o  = float(curr["open"])
    c_c  = float(curr["close"])
    c_h  = float(curr["high"])
    c_l  = float(curr["low"])

    c_range = c_h - c_l
    if c_range == 0:
        return None

    touching = c_l <= zone_top and c_h >= zone_bottom
    if not touching:
        return None

    if direction == "LONG":
        wick = min(c_o, c_c) - c_l
        if wick / c_range < HE["trigger_min_wick_ratio"]:
            return None
        if c_c < (c_h + c_l) / 2:
            return None
        if c_c < zone_bottom:
            return None
    else:
        wick = c_h - max(c_o, c_c)
        if wick / c_range < HE["trigger_min_wick_ratio"]:
            return None
        if c_c > (c_h + c_l) / 2:
            return None
        if c_c > zone_top:
            return None

    return {
        "pattern_score": 0.85,
        "entry_price":   round(c_c, 6),
        "candle_high":   round(c_h, 6),
        "candle_low":    round(c_l, 6),
    }


def _rejected(
    reason:        str,
    sweep_score:   float,
    zone_score:    float,
    trigger_score: float,
    sweep:         object,
    zone:          object,
) -> ICTResult:
    return ICTResult(
        confirmed     = False,
        score         = 0.0,
        sweep_score   = sweep_score,
        zone_score    = zone_score,
        trigger_score = trigger_score,
        entry_price   = 0.0,
        candle_high   = 0.0,
        candle_low    = 0.0,
        sweep         = sweep,
        zone          = zone,
        trigger       = TriggerData(
            confirmed   = False,
            pattern     = "",
            score       = 0.0,
            entry_price = 0.0,
            candle_high = 0.0,
            candle_low  = 0.0,
            vol_mult    = 0.0,
            reason      = reason,
        ),
        displacement  = {"found": False, "score": 0.0},
        reason        = reason,
        desc          = reason,
    )


from typing import Optional