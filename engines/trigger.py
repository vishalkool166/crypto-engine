import time
import logging
import pandas as pd
from config import cfg

log = logging.getLogger(__name__)


def check_15m_trigger(
    df_15m:    pd.DataFrame,
    zone:      dict,
    direction: str,
    atr_4h:    float
) -> dict:
    se = cfg.SIGNAL_ENGINE

    if df_15m is None or len(df_15m) < 10:
        return _no_trigger("insufficient_data")

    price  = float(df_15m["close"].iloc[-1])
    buffer = atr_4h * se["sl_buffer_atr_mult"]

    if not _price_near_zone(price, zone, buffer):
        return _no_trigger("price_outside_zone")

    recent = df_15m.tail(se["trigger_lookback"])

    result = (
        _check_engulfing(recent, zone, direction, buffer, se) or
        _check_pin_bar(recent, zone, direction, buffer, se)
    )

    if not result:
        return _no_trigger("no_pattern")

    return result


def _price_near_zone(price: float, zone: dict, buffer: float) -> bool:
    return (zone["bottom"] - buffer) <= price <= (zone["top"] + buffer)


def _check_engulfing(
    df:        pd.DataFrame,
    zone:      dict,
    direction: str,
    buffer:    float,
    se:        dict
) -> dict | None:
    if len(df) < 2:
        return None

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    c_open  = float(curr["open"])
    c_close = float(curr["close"])
    c_high  = float(curr["high"])
    c_low   = float(curr["low"])
    c_body  = abs(c_close - c_open)
    c_range = c_high - c_low

    p_open  = float(prev["open"])
    p_close = float(prev["close"])

    if c_range == 0:
        return None
    if c_body / c_range < se["trigger_min_body_ratio"]:
        return None
    if not _candle_touches_zone(c_high, c_low, zone, buffer):
        return None

    if direction == "LONG":
        if not (p_close < p_open):
            return None
        if not (c_close > c_open):
            return None
        if not (c_close > p_open and c_open < p_close):
            return None
        if not (c_close >= zone["bottom"]):
            return None
    else:
        if not (p_close > p_open):
            return None
        if not (c_close < c_open):
            return None
        if not (c_close < p_open and c_open > p_close):
            return None
        if not (c_close <= zone["top"]):
            return None

    return {
        "confirmed":    True,
        "pattern":      "engulfing",
        "entry_price":  round(c_close, 6),
        "candle_high":  round(c_high, 6),
        "candle_low":   round(c_low, 6),
        "body_ratio":   round(c_body / c_range, 3),
        "triggered_at": time.time(),
    }


def _check_pin_bar(
    df:        pd.DataFrame,
    zone:      dict,
    direction: str,
    buffer:    float,
    se:        dict
) -> dict | None:
    if len(df) < 1:
        return None

    curr    = df.iloc[-1]
    c_open  = float(curr["open"])
    c_close = float(curr["close"])
    c_high  = float(curr["high"])
    c_low   = float(curr["low"])
    c_range = c_high - c_low

    if c_range == 0:
        return None
    if not _candle_touches_zone(c_high, c_low, zone, buffer):
        return None

    if direction == "LONG":
        wick = min(c_open, c_close) - c_low
        if wick / c_range < se["trigger_min_wick_ratio"]:
            return None
        if c_close < (c_high + c_low) / 2:
            return None
        if c_close < zone["bottom"] - buffer:
            return None
    else:
        wick = c_high - max(c_open, c_close)
        if wick / c_range < se["trigger_min_wick_ratio"]:
            return None
        if c_close > (c_high + c_low) / 2:
            return None
        if c_close > zone["top"] + buffer:
            return None

    return {
        "confirmed":    True,
        "pattern":      "pin_bar",
        "entry_price":  round(c_close, 6),
        "candle_high":  round(c_high, 6),
        "candle_low":   round(c_low, 6),
        "wick_ratio":   round(wick / c_range, 3),
        "triggered_at": time.time(),
    }


def _candle_touches_zone(
    high:      float,
    low:       float,
    zone:      dict,
    buffer:    float
) -> bool:
    return (
        low  <= zone["top"]    + buffer and
        high >= zone["bottom"] - buffer
    )


def _no_trigger(reason: str) -> dict:
    return {
        "confirmed":    False,
        "pattern":      None,
        "entry_price":  None,
        "candle_high":  None,
        "candle_low":   None,
        "reason":       reason,
        "triggered_at": None,
    }