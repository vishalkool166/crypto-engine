import pandas as pd
from typing import Optional


def detect_order_blocks(
    df:        pd.DataFrame,
    atr:       float,
    lookback:  int = 50
) -> dict:

    if df is None or len(df) < 10:
        return _empty_result()

    if not atr or atr <= 0:
        atr = float(df["close"].iloc[-1]) * 0.015

    price   = float(df["close"].iloc[-1])
    sl      = df.tail(lookback).copy()
    n       = len(sl)

    bull_obs = []
    bear_obs = []
    breakers = []

    for i in range(2, n - 3):
        c       = sl.iloc[i]
        c_open  = float(c["open"])
        c_close = float(c["close"])
        c_high  = float(c["high"])
        c_low   = float(c["low"])
        c_body  = abs(c_close - c_open)
        c_range = c_high - c_low

        if c_range == 0:
            continue

        is_bearish = c_close < c_open
        if is_bearish:
            next3      = sl.iloc[i+1:i+4]
            impulse_up = _check_impulse(next3, "bull", atr)

            if impulse_up:
                ob_top    = max(c_open, c_close)
                ob_bottom = min(c_open, c_close)
                ob_mid    = (ob_top + ob_bottom) / 2

                in_zone    = ob_bottom <= price <= ob_top
                approaching = ob_bottom * 0.98 <= price <= ob_top * 1.02
                above_zone = price > ob_top
                below_zone = price < ob_bottom

                future_candles = sl.iloc[i+1:]
                touch_count    = _count_touches(future_candles, ob_top, ob_bottom, "bull")
                mitigated      = _check_mitigation(future_candles, ob_top, ob_bottom, "bull")

                strength = _ob_strength(c, next3, atr, "bull")
                strength = max(0.0, strength - (touch_count * strength * 0.2))

                ob = {
                    "type":        "bull",
                    "top":         round(ob_top, 6),
                    "bottom":      round(ob_bottom, 6),
                    "mid":         round(ob_mid, 6),
                    "candle_idx":  i,
                    "candles_ago": n - 1 - i,
                    "body_size":   round(c_body, 6),
                    "range_size":  round(c_range, 6),
                    "impulse":     impulse_up,
                    "mitigated":   mitigated,
                    "in_zone":     in_zone,
                    "approaching": approaching,
                    "above_zone":  above_zone,
                    "below_zone":  below_zone,
                    "strength":    strength,
                    "touch_count": touch_count,
                    "weak":        touch_count >= 3,
                    "label":       "Bullish OB",
                    "desc":        f"Bull OB @ {ob_bottom:.2f}-{ob_top:.2f}"
                }

                if mitigated:
                    ob["label"]        = "Breaker (was Bull OB)"
                    ob["breaker_type"] = "bear"
                    breakers.append(ob)
                else:
                    bull_obs.append(ob)

        is_bullish = c_close > c_open
        if is_bullish:
            next3        = sl.iloc[i+1:i+4]
            impulse_down = _check_impulse(next3, "bear", atr)

            if impulse_down:
                ob_top    = max(c_open, c_close)
                ob_bottom = min(c_open, c_close)
                ob_mid    = (ob_top + ob_bottom) / 2

                in_zone    = ob_bottom <= price <= ob_top
                approaching = ob_bottom * 0.98 <= price <= ob_top * 1.02
                above_zone = price > ob_top
                below_zone = price < ob_bottom

                future_candles = sl.iloc[i+1:]
                touch_count    = _count_touches(future_candles, ob_top, ob_bottom, "bear")
                mitigated      = _check_mitigation(future_candles, ob_top, ob_bottom, "bear")

                strength = _ob_strength(c, next3, atr, "bear")
                strength = max(0.0, strength - (touch_count * strength * 0.2))

                ob = {
                    "type":        "bear",
                    "top":         round(ob_top, 6),
                    "bottom":      round(ob_bottom, 6),
                    "mid":         round(ob_mid, 6),
                    "candle_idx":  i,
                    "candles_ago": n - 1 - i,
                    "body_size":   round(c_body, 6),
                    "range_size":  round(c_range, 6),
                    "impulse":     impulse_down,
                    "mitigated":   mitigated,
                    "in_zone":     in_zone,
                    "approaching": approaching,
                    "above_zone":  above_zone,
                    "below_zone":  below_zone,
                    "strength":    strength,
                    "touch_count": touch_count,
                    "weak":        touch_count >= 3,
                    "label":       "Bearish OB",
                    "desc":        f"Bear OB @ {ob_bottom:.2f}-{ob_top:.2f}"
                }

                if mitigated:
                    ob["label"]        = "Breaker (was Bear OB)"
                    ob["breaker_type"] = "bull"
                    breakers.append(ob)
                else:
                    bear_obs.append(ob)

    bull_obs.sort(
        key=lambda x: (
            x["strength"] * 0.6 +
            (1 / max(x["candles_ago"], 1)) * 0.4
        ),
        reverse=True
    )
    bear_obs.sort(
        key=lambda x: (
            x["strength"] * 0.6 +
            (1 / max(x["candles_ago"], 1)) * 0.4
        ),
        reverse=True
    )

    nearest_bull = _find_nearest(bull_obs, price, "bull")
    nearest_bear = _find_nearest(bear_obs, price, "bear")

    score = _score_obs(nearest_bull, nearest_bear, price, breakers)

    return {
        "bull_obs":     bull_obs[:5],
        "bear_obs":     bear_obs[:5],
        "breakers":     breakers[:3],
        "nearest_bull": nearest_bull,
        "nearest_bear": nearest_bear,
        "score":        score,
        "has_bull":     len(bull_obs) > 0,
        "has_bear":     len(bear_obs) > 0,
        "price":        price,
        "label":        _get_label(nearest_bull, nearest_bear, price),
        "desc":         _get_desc(nearest_bull, nearest_bear, price)
    }


def _count_touches(
    future_candles: pd.DataFrame,
    ob_top:         float,
    ob_bottom:      float,
    ob_type:        str
) -> int:
    touches = 0
    for _, c in future_candles.iterrows():
        h = float(c["high"])
        l = float(c["low"])
        if l <= ob_top and h >= ob_bottom:
            touches += 1
    return touches


def _check_impulse(
    next_candles: pd.DataFrame,
    direction:    str,
    atr:          float
) -> dict:
    if len(next_candles) < 2:
        return None

    total_move = 0
    bull_count = 0
    bear_count = 0

    for _, c in next_candles.iterrows():
        move = float(c["close"]) - float(c["open"])
        total_move += move
        if move > 0:
            bull_count += 1
        else:
            bear_count += 1

    if direction == "bull":
        if total_move > atr * 0.8 and bull_count >= 1:
            return {
                "direction": "bull",
                "magnitude": round(total_move, 4),
                "atr_mult":  round(total_move / atr, 2) if atr > 0 else 0
            }
    else:
        if total_move < -atr * 0.8 and bear_count >= 1:
            return {
                "direction": "bear",
                "magnitude": round(abs(total_move), 4),
                "atr_mult":  round(abs(total_move) / atr, 2) if atr > 0 else 0
            }

    return None


def _check_mitigation(
    future_candles: pd.DataFrame,
    ob_top:         float,
    ob_bottom:      float,
    ob_type:        str
) -> bool:
    for _, c in future_candles.iterrows():
        if ob_type == "bull":
            if float(c["close"]) < ob_bottom:
                return True
        else:
            if float(c["close"]) > ob_top:
                return True
    return False


def _ob_strength(
    ob_candle:    pd.Series,
    next_candles: pd.DataFrame,
    atr:          float,
    ob_type:      str
) -> float:
    score = 0.0

    c_open  = float(ob_candle["open"])
    c_close = float(ob_candle["close"])
    c_high  = float(ob_candle["high"])
    c_low   = float(ob_candle["low"])
    body    = abs(c_close - c_open)
    rng     = c_high - c_low

    if rng > 0:
        score += (body / rng) * 3

    if atr > 0:
        score += min(rng / atr * 2, 3)

    total_impulse = 0
    for _, c in next_candles.iterrows():
        move = float(c["close"]) - float(c["open"])
        if ob_type == "bull":
            total_impulse += max(move, 0)
        else:
            total_impulse += max(-move, 0)

    if atr > 0:
        score += min(total_impulse / atr * 2, 4)

    return round(min(score, 10), 2)


def _find_nearest(
    obs:     list,
    price:   float,
    ob_type: str
) -> Optional[dict]:
    if not obs:
        return None

    relevant = []
    for ob in obs:
        if ob.get("weak"):
            continue
        if ob_type == "bull":
            if ob["top"] <= price * 1.02:
                dist = abs(price - ob["mid"])
                relevant.append((dist, ob))
        else:
            if ob["bottom"] >= price * 0.98:
                dist = abs(price - ob["mid"])
                relevant.append((dist, ob))

    if not relevant:
        return None

    relevant.sort(key=lambda x: x[0])
    return relevant[0][1]


def _score_obs(
    nearest_bull: Optional[dict],
    nearest_bear: Optional[dict],
    price:        float,
    breakers:     list
) -> float:
    score = 0.0

    if nearest_bull:
        if nearest_bull["in_zone"]:
            score += 8
        elif nearest_bull["approaching"]:
            score += 5
        else:
            score += 2
        score += nearest_bull["strength"] * 0.2

    if nearest_bear:
        if nearest_bear["in_zone"]:
            score += 8
        elif nearest_bear["approaching"]:
            score += 5
        else:
            score += 2
        score += nearest_bear["strength"] * 0.2

    for b in breakers:
        if b.get("in_zone") or b.get("approaching"):
            score += 3

    return round(min(score, 10), 2)


def _get_label(
    nearest_bull: Optional[dict],
    nearest_bear: Optional[dict],
    price:        float
) -> str:
    if nearest_bull and nearest_bull["in_zone"]:
        return "✅ In Bullish OB"
    if nearest_bear and nearest_bear["in_zone"]:
        return "✅ In Bearish OB"
    if nearest_bull and nearest_bull["approaching"]:
        return "⚡ Approaching Bull OB"
    if nearest_bear and nearest_bear["approaching"]:
        return "⚡ Approaching Bear OB"
    if nearest_bull or nearest_bear:
        return "📍 OB Identified"
    return "❌ No OB detected"


def _get_desc(
    nearest_bull: Optional[dict],
    nearest_bear: Optional[dict],
    price:        float
) -> str:
    parts = []
    if nearest_bull:
        parts.append(
            f"Bull OB: {nearest_bull['bottom']:.2f}-{nearest_bull['top']:.2f} "
            f"(str:{nearest_bull['strength']} touches:{nearest_bull['touch_count']})"
        )
    if nearest_bear:
        parts.append(
            f"Bear OB: {nearest_bear['bottom']:.2f}-{nearest_bear['top']:.2f} "
            f"(str:{nearest_bear['strength']} touches:{nearest_bear['touch_count']})"
        )
    return " · ".join(parts) if parts else "None"


def _empty_result() -> dict:
    return {
        "bull_obs":     [],
        "bear_obs":     [],
        "breakers":     [],
        "nearest_bull": None,
        "nearest_bear": None,
        "score":        0,
        "has_bull":     False,
        "has_bear":     False,
        "price":        0,
        "label":        "❌ No OB detected",
        "desc":         "Not enough data"
    }