import pandas as pd
from typing import Optional

# ═══════════════════════════════════════════════════════
# ORDER BLOCK DETECTION
# ICT concept — institutional order blocks
# where smart money placed large orders
# price returns to these zones for continuation
# ═══════════════════════════════════════════════════════


def detect_order_blocks(
    df:        pd.DataFrame,
    atr:       float,
    lookback:  int = 50
) -> dict:
    """
    Detects bullish and bearish order blocks.

    Bullish OB:
    - Last bearish candle before strong bullish move
    - Price returns to this zone = long entry

    Bearish OB:
    - Last bullish candle before strong bearish move
    - Price returns to this zone = short entry

    Breaker Block:
    - OB that price has broken through
    - Now acts as opposite zone
    """

    if df is None or len(df) < 10:
        return _empty_result()

    if not atr or atr <= 0:
        atr = float(df["close"].iloc[-1]) * 0.015

    price   = float(df["close"].iloc[-1])
    sl      = df.tail(lookback).copy()
    n       = len(sl)

    bull_obs    = []
    bear_obs    = []
    breakers    = []

    # ── SCAN FOR ORDER BLOCKS ──
    for i in range(2, n - 3):
        c     = sl.iloc[i]
        c_open  = float(c["open"])
        c_close = float(c["close"])
        c_high  = float(c["high"])
        c_low   = float(c["low"])
        c_body  = abs(c_close - c_open)
        c_range = c_high - c_low

        if c_range == 0:
            continue

        # ── BULLISH ORDER BLOCK ──
        # Last bearish candle before impulse up
        is_bearish = c_close < c_open

        if is_bearish:
            # Check if followed by strong bullish move
            next3 = sl.iloc[i+1:i+4]
            impulse_up = _check_impulse(
                next3, "bull", atr
            )

            if impulse_up:
                # This bearish candle is a bullish OB
                ob_top    = max(c_open, c_close)
                ob_bottom = min(c_open, c_close)
                ob_mid    = (ob_top + ob_bottom) / 2

                # Check if price is near or in zone
                in_zone    = ob_bottom <= price <= ob_top
                approaching = (
                    ob_bottom * 0.98 <= price <= ob_top * 1.02
                )
                above_zone = price > ob_top
                below_zone = price < ob_bottom

                # Check if OB has been mitigated
                # (price already traded through it)
                mitigated = _check_mitigation(
                    sl.iloc[i+1:],
                    ob_top,
                    ob_bottom,
                    "bull"
                )

                # Strength score
                strength = _ob_strength(
                    c, next3, atr, "bull"
                )

                ob = {
                    "type":       "bull",
                    "top":        round(ob_top, 6),
                    "bottom":     round(ob_bottom, 6),
                    "mid":        round(ob_mid, 6),
                    "candle_idx": i,
                    "candles_ago": n - 1 - i,
                    "body_size":  round(c_body, 6),
                    "range_size": round(c_range, 6),
                    "impulse":    impulse_up,
                    "mitigated":  mitigated,
                    "in_zone":    in_zone,
                    "approaching": approaching,
                    "above_zone": above_zone,
                    "below_zone": below_zone,
                    "strength":   strength,
                    "label":      "Bullish OB",
                    "desc": (
                        f"Bull OB @ "
                        f"{ob_bottom:.2f}-{ob_top:.2f}"
                    )
                }

                if mitigated:
                    # Becomes a breaker block
                    # now acts as bearish zone
                    ob["label"] = "Breaker (was Bull OB)"
                    ob["breaker_type"] = "bear"
                    breakers.append(ob)
                else:
                    bull_obs.append(ob)

        # ── BEARISH ORDER BLOCK ──
        # Last bullish candle before impulse down
        is_bullish = c_close > c_open

        if is_bullish:
            # Check if followed by strong bearish move
            next3 = sl.iloc[i+1:i+4]
            impulse_down = _check_impulse(
                next3, "bear", atr
            )

            if impulse_down:
                ob_top    = max(c_open, c_close)
                ob_bottom = min(c_open, c_close)
                ob_mid    = (ob_top + ob_bottom) / 2

                in_zone    = ob_bottom <= price <= ob_top
                approaching = (
                    ob_bottom * 0.98 <= price <= ob_top * 1.02
                )
                above_zone = price > ob_top
                below_zone = price < ob_bottom

                mitigated = _check_mitigation(
                    sl.iloc[i+1:],
                    ob_top,
                    ob_bottom,
                    "bear"
                )

                strength = _ob_strength(
                    c, next3, atr, "bear"
                )

                ob = {
                    "type":       "bear",
                    "top":        round(ob_top, 6),
                    "bottom":     round(ob_bottom, 6),
                    "mid":        round(ob_mid, 6),
                    "candle_idx": i,
                    "candles_ago": n - 1 - i,
                    "body_size":  round(c_body, 6),
                    "range_size": round(c_range, 6),
                    "impulse":    impulse_down,
                    "mitigated":  mitigated,
                    "in_zone":    in_zone,
                    "approaching": approaching,
                    "above_zone": above_zone,
                    "below_zone": below_zone,
                    "strength":   strength,
                    "label":      "Bearish OB",
                    "desc": (
                        f"Bear OB @ "
                        f"{ob_bottom:.2f}-{ob_top:.2f}"
                    )
                }

                if mitigated:
                    ob["label"] = "Breaker (was Bear OB)"
                    ob["breaker_type"] = "bull"
                    breakers.append(ob)
                else:
                    bear_obs.append(ob)

    # ── SORT BY RELEVANCE ──
    # Most recent + strongest first
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

    # ── FIND NEAREST ACTIVE OB ──
    nearest_bull = _find_nearest(
        bull_obs, price, "bull"
    )
    nearest_bear = _find_nearest(
        bear_obs, price, "bear"
    )

    # ── SCORE ──
    score = _score_obs(
        nearest_bull,
        nearest_bear,
        price,
        breakers
    )

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
        "label":        _get_label(
            nearest_bull, nearest_bear, price
        ),
        "desc":         _get_desc(
            nearest_bull, nearest_bear, price
        )
    }


# ═══════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════

def _check_impulse(
    next_candles: pd.DataFrame,
    direction:    str,
    atr:          float
) -> dict:
    """
    Checks if next candles show impulse move.
    Returns impulse details or None.
    """
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
        # Need net upward move > 1x ATR
        if total_move > atr * 0.8 and bull_count >= 1:
            return {
                "direction": "bull",
                "magnitude": round(total_move, 4),
                "atr_mult":  round(total_move / atr, 2)
                             if atr > 0 else 0
            }
    else:
        # Need net downward move > 1x ATR
        if total_move < -atr * 0.8 and bear_count >= 1:
            return {
                "direction": "bear",
                "magnitude": round(abs(total_move), 4),
                "atr_mult":  round(
                    abs(total_move) / atr, 2
                ) if atr > 0 else 0
            }

    return None


def _check_mitigation(
    future_candles: pd.DataFrame,
    ob_top:         float,
    ob_bottom:      float,
    ob_type:        str
) -> bool:
    """
    Checks if price has already traded
    through the order block zone.
    Mitigated OB = no longer valid entry zone.
    """
    for _, c in future_candles.iterrows():
        if ob_type == "bull":
            # Bull OB mitigated if price
            # closed below the bottom
            if float(c["close"]) < ob_bottom:
                return True
        else:
            # Bear OB mitigated if price
            # closed above the top
            if float(c["close"]) > ob_top:
                return True
    return False


def _ob_strength(
    ob_candle:    pd.Series,
    next_candles: pd.DataFrame,
    atr:          float,
    ob_type:      str
) -> float:
    """
    Scores OB strength 0-10.
    Based on:
    - Body size relative to ATR
    - Impulse magnitude after OB
    - Volume if available
    """
    score = 0.0

    c_open  = float(ob_candle["open"])
    c_close = float(ob_candle["close"])
    c_high  = float(ob_candle["high"])
    c_low   = float(ob_candle["low"])
    body    = abs(c_close - c_open)
    rng     = c_high - c_low

    # Body ratio
    if rng > 0:
        body_ratio = body / rng
        score += body_ratio * 3  # max 3

    # ATR relative size
    if atr > 0:
        atr_ratio = rng / atr
        score += min(atr_ratio * 2, 3)  # max 3

    # Impulse after
    total_impulse = 0
    for _, c in next_candles.iterrows():
        move = float(c["close"]) - float(c["open"])
        if ob_type == "bull":
            total_impulse += max(move, 0)
        else:
            total_impulse += max(-move, 0)

    if atr > 0:
        imp_ratio = total_impulse / atr
        score += min(imp_ratio * 2, 4)  # max 4

    return round(min(score, 10), 2)


def _find_nearest(
    obs:       list,
    price:     float,
    ob_type:   str
) -> Optional[dict]:
    """
    Finds the nearest relevant OB to current price.
    For bull OB — nearest below price
    For bear OB — nearest above price
    """
    if not obs:
        return None

    relevant = []
    for ob in obs:
        if ob_type == "bull":
            # Bull OB should be below or at price
            if ob["top"] <= price * 1.02:
                dist = abs(price - ob["mid"])
                relevant.append((dist, ob))
        else:
            # Bear OB should be above or at price
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
    """
    Scores overall OB confluence 0-10.
    """
    score = 0.0

    if nearest_bull:
        # In zone = highest score
        if nearest_bull["in_zone"]:
            score += 8
        elif nearest_bull["approaching"]:
            score += 5
        else:
            score += 2
        # Add strength bonus
        score += nearest_bull["strength"] * 0.2

    if nearest_bear:
        if nearest_bear["in_zone"]:
            score += 8
        elif nearest_bear["approaching"]:
            score += 5
        else:
            score += 2
        score += nearest_bear["strength"] * 0.2

    # Breaker blocks add confluence
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
            f"Bull OB: "
            f"{nearest_bull['bottom']:.2f}"
            f"-{nearest_bull['top']:.2f} "
            f"(str:{nearest_bull['strength']})"
        )
    if nearest_bear:
        parts.append(
            f"Bear OB: "
            f"{nearest_bear['bottom']:.2f}"
            f"-{nearest_bear['top']:.2f} "
            f"(str:{nearest_bear['strength']})"
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