import time
import logging
import pandas as pd
from config import cfg

log = logging.getLogger(__name__)

SE = cfg.SCALP_ENGINE

TF_HOURS = {"15m": 0.25, "1h": 1.0, "4h": 4.0, "1d": 24.0}


def _find_levels(df: pd.DataFrame, swings: dict) -> list:
    price    = float(df["close"].iloc[-1])
    levels   = []
    highs    = swings.get("highs", [])
    lows     = swings.get("lows",  [])

    if swings.get("last_low"):
        levels.append({"price": swings["last_low"]["price"],  "type": "swing_low",  "priority": 2})
    if swings.get("prev_low"):
        levels.append({"price": swings["prev_low"]["price"],  "type": "swing_low",  "priority": 2})
    if swings.get("last_high"):
        levels.append({"price": swings["last_high"]["price"], "type": "swing_high", "priority": 2})
    if swings.get("prev_high"):
        levels.append({"price": swings["prev_high"]["price"], "type": "swing_high", "priority": 2})

    if len(lows) >= 2:
        for i in range(len(lows) - 1):
            a = lows[i]["price"]
            b = lows[i + 1]["price"]
            if abs(a - b) / b < 0.001:
                levels.append({"price": min(a, b), "type": "equal_lows", "priority": 1})

    if len(highs) >= 2:
        for i in range(len(highs) - 1):
            a = highs[i]["price"]
            b = highs[i + 1]["price"]
            if abs(a - b) / b < 0.001:
                levels.append({"price": max(a, b), "type": "equal_highs", "priority": 1})

    round_levels = []
    magnitude    = price / 100
    step         = 10 ** (len(str(int(magnitude))) - 1)
    base         = round(price / step) * step
    for mult in range(-5, 6):
        lvl = base + mult * step
        if lvl > 0:
            round_levels.append({"price": lvl, "type": "round_number", "priority": 3})
    levels.extend(round_levels)

    return levels


def _check_sweep_below(df: pd.DataFrame, level: float, atr: float, lookback: int = 20) -> dict | None:
    sl      = df.tail(lookback)
    vol_ma  = float(df["volume"].rolling(20).mean().iloc[-1]) or 1
    price   = float(df["close"].iloc[-1])
    hours_per_candle = TF_HOURS.get("1h", 1.0)

    for i in range(len(sl) - 1):
        c = sl.iloc[i]
        if float(c["low"]) < level and float(c["close"]) > level:
            wick        = level - float(c["low"])
            if wick < atr * SE["sweep_min_wick_atr"]:
                continue
            candles_ago = len(sl) - 1 - i
            age_hours   = candles_ago * hours_per_candle
            if age_hours > SE["sweep_max_age_hours"]:
                continue
            vol_ratio   = float(c["volume"]) / vol_ma
            confirmed   = price > level

            age_mult = (
                1.0  if age_hours <= 2 else
                0.85 if age_hours <= 4 else
                0.65 if age_hours <= 6 else
                0.45
            )
            vol_mult = (
                1.2 if vol_ratio >= 1.5 else
                1.0 if vol_ratio >= 1.0 else
                0.8
            )
            base_score = min(wick / atr, 2.0) / 2.0
            score      = base_score * age_mult * vol_mult
            if not confirmed:
                score *= 0.4

            return {
                "type":        "bull",
                "level":       float(level),
                "sweep_low":   float(c["low"]),
                "sweep_high":  None,
                "wick":        round(wick, 6),
                "wick_atr":    round(wick / atr, 2),
                "age_hours":   round(age_hours, 1),
                "vol_ratio":   round(vol_ratio, 2),
                "confirmed":   confirmed,
                "score":       round(score, 3),
                "candles_ago": candles_ago,
            }
    return None


def _check_sweep_above(df: pd.DataFrame, level: float, atr: float, lookback: int = 20) -> dict | None:
    sl      = df.tail(lookback)
    vol_ma  = float(df["volume"].rolling(20).mean().iloc[-1]) or 1
    price   = float(df["close"].iloc[-1])
    hours_per_candle = TF_HOURS.get("1h", 1.0)

    for i in range(len(sl) - 1):
        c = sl.iloc[i]
        if float(c["high"]) > level and float(c["close"]) < level:
            wick        = float(c["high"]) - level
            if wick < atr * SE["sweep_min_wick_atr"]:
                continue
            candles_ago = len(sl) - 1 - i
            age_hours   = candles_ago * hours_per_candle
            if age_hours > SE["sweep_max_age_hours"]:
                continue
            vol_ratio   = float(c["volume"]) / vol_ma
            confirmed   = price < level

            age_mult = (
                1.0  if age_hours <= 2 else
                0.85 if age_hours <= 4 else
                0.65 if age_hours <= 6 else
                0.45
            )
            vol_mult = (
                1.2 if vol_ratio >= 1.5 else
                1.0 if vol_ratio >= 1.0 else
                0.8
            )
            base_score = min(wick / atr, 2.0) / 2.0
            score      = base_score * age_mult * vol_mult
            if not confirmed:
                score *= 0.4

            return {
                "type":        "bear",
                "level":       float(level),
                "sweep_low":   None,
                "sweep_high":  float(c["high"]),
                "wick":        round(wick, 6),
                "wick_atr":    round(wick / atr, 2),
                "age_hours":   round(age_hours, 1),
                "vol_ratio":   round(vol_ratio, 2),
                "confirmed":   confirmed,
                "score":       round(score, 3),
                "candles_ago": candles_ago,
            }
    return None


def detect(df_1h: pd.DataFrame, d1h: dict, direction: str) -> dict:
    atr    = d1h.get("atr")
    swings = d1h.get("swings", {})

    if not atr or atr <= 0:
        atr = float(df_1h["close"].iloc[-1]) * 0.01

    levels  = _find_levels(df_1h, swings)
    results = []

    for lvl in levels:
        level_price = lvl["price"]
        priority    = lvl["priority"]
        level_type  = lvl["type"]

        if direction == "LONG":
            result = _check_sweep_below(df_1h, level_price, atr)
        else:
            result = _check_sweep_above(df_1h, level_price, atr)

        if result and result["score"] >= SE["sweep_min_score"]:
            result["level_type"] = level_type
            result["level_label"] = level_type.replace("_", " ").title()
            result["priority"]   = priority
            result["score"]     *= (1.0 if priority == 1 else 0.9 if priority == 2 else 0.8)
            result["score"]      = round(result["score"], 3)
            results.append(result)

    if not results:
        return {"detected": False, "score": 0.0, "sweep": None}

    results.sort(key=lambda x: (x["priority"], -x["score"]))
    best = results[0]

    return {
        "detected":    True,
        "score":       best["score"],
        "sweep":       best,
        "all_sweeps":  results,
    }