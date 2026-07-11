import time
import logging
import pandas as pd
from config import cfg

log = logging.getLogger(__name__)

SE = cfg.SCALP_ENGINE


def _vol_score(df: pd.DataFrame) -> float:
    vol_ma  = float(df["volume"].rolling(20).mean().iloc[-1]) or 1
    cur_vol = float(df["volume"].iloc[-1])
    ratio   = cur_vol / vol_ma
    return (
        1.2 if ratio >= 1.5 else
        1.0 if ratio >= 1.1 else
        0.85 if ratio >= 0.8 else
        0.7
    )


def _near_zone(price: float, zone: dict, atr_15m: float) -> bool:
    buffer = atr_15m * 1.5
    return (zone["bottom"] - buffer) <= price <= (zone["top"] + buffer)


def _check_engulfing(df: pd.DataFrame, direction: str, zone: dict) -> dict | None:
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
    if c_body / c_range < SE["trigger_min_body_ratio"]:
        return None

    touching = c_l <= zone["top"] and c_h >= zone["bottom"]
    if not touching:
        return None

    if direction == "LONG":
        if not (p_c < p_o and c_c > c_o):
            return None
        if not (c_c > p_o and c_o < p_c):
            return None
        if c_c < zone["bottom"]:
            return None
    else:
        if not (p_c > p_o and c_c < c_o):
            return None
        if not (c_c < p_o and c_o > p_c):
            return None
        if c_c > zone["top"]:
            return None

    return {
        "pattern":      "engulfing",
        "body_ratio":   round(c_body / c_range, 3),
        "entry_price":  round(c_c, 6),
        "candle_high":  round(c_h, 6),
        "candle_low":   round(c_l, 6),
        "pattern_score": 1.0,
    }


def _check_pin_bar(df: pd.DataFrame, direction: str, zone: dict) -> dict | None:
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

    touching = c_l <= zone["top"] and c_h >= zone["bottom"]
    if not touching:
        return None

    if direction == "LONG":
        wick = min(c_o, c_c) - c_l
        if wick / c_range < SE["trigger_min_wick_ratio"]:
            return None
        if c_c < (c_h + c_l) / 2:
            return None
        if c_c < zone["bottom"]:
            return None
    else:
        wick = c_h - max(c_o, c_c)
        if wick / c_range < SE["trigger_min_wick_ratio"]:
            return None
        if c_c > (c_h + c_l) / 2:
            return None
        if c_c > zone["top"]:
            return None

    return {
        "pattern":       "pin_bar",
        "wick_ratio":    round(wick / c_range, 3),
        "entry_price":   round(c_c, 6),
        "candle_high":   round(c_h, 6),
        "candle_low":    round(c_l, 6),
        "pattern_score": 0.85,
    }


def detect(df_15m: pd.DataFrame, zone: dict, direction: str, atr_15m: float) -> dict:
    if df_15m is None or len(df_15m) < SE["trigger_lookback"]:
        return {"confirmed": False, "score": 0.0, "pattern": None, "reason": "insufficient_data"}

    price = float(df_15m["close"].iloc[-1])

    if not _near_zone(price, zone, atr_15m):
        return {"confirmed": False, "score": 0.0, "pattern": None, "reason": "price_outside_zone"}

    recent = df_15m.tail(SE["trigger_lookback"])

    result = (
        _check_engulfing(recent, direction, zone) or
        _check_pin_bar(recent,   direction, zone)
    )

    if not result:
        return {"confirmed": False, "score": 0.0, "pattern": None, "reason": "no_pattern"}

    vol_mult = _vol_score(df_15m)
    score    = round(result["pattern_score"] * vol_mult, 3)

    if score < SE["trigger_min_score"]:
        return {"confirmed": False, "score": score, "pattern": result["pattern"], "reason": "score_too_low"}

    return {
        "confirmed":    True,
        "score":        score,
        "pattern":      result["pattern"],
        "entry_price":  result["entry_price"],
        "candle_high":  result["candle_high"],
        "candle_low":   result["candle_low"],
        "vol_mult":     vol_mult,
        "triggered_at": time.time(),
        "reason":       "",
    }