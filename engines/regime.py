from config import cfg


def detect_regime(d1d: dict, d4h: dict) -> dict:
    adx_1d = d1d.get("adx")
    adx_4h = d4h.get("adx")
    bb_1d  = d1d.get("bb")
    s20    = d1d.get("slope20")
    s50    = d1d.get("slope50")
    trend  = d1d.get("trend", {})

    if (adx_1d is not None and adx_4h is not None and
            adx_1d < 18 and adx_4h < 18):
        return {
            "type":           "chop",
            "tradeable":      False,
            "score":          0,
            "label":          "CHOPPY MARKET",
            "desc":           "ADX weak on 1D+4H. No trend.",
            "atr_multiplier": 2.0
        }

    flat = (
        s20 is not None and abs(s20) < 0.15 and
        s50 is not None and abs(s50) < 0.15
    )
    if (adx_1d is not None and adx_1d < 25 and
            bb_1d and bb_1d["width"] < 3 and flat):
        return {
            "type":           "ranging",
            "tradeable":      False,
            "score":          3,
            "label":          "RANGING",
            "desc":           "Low ADX + narrow BB + flat EMAs.",
            "atr_multiplier": 1.5
        }

    if (bb_1d and bb_1d["width"] > 8 and
            d1d["cur_vol"] > d1d["vol_ma5"] * 1.8):
        return {
            "type":           "expansion",
            "tradeable":      True,
            "score":          7,
            "label":          "VOLATILITY EXPANSION",
            "desc":           "BB wide + volume spike. Breakout mode.",
            "atr_multiplier": 2.5
        }

    if trend.get("cls") == "bull" and adx_1d and adx_1d >= 25:
        return {
            "type":           "trending-bull",
            "tradeable":      True,
            "score":          10,
            "label":          "TRENDING BULLISH",
            "desc":           "Strong uptrend. Use continuation logic.",
            "atr_multiplier": 2.0
        }

    if trend.get("cls") == "bear" and adx_1d and adx_1d >= 25:
        return {
            "type":           "trending-bear",
            "tradeable":      True,
            "score":          10,
            "label":          "TRENDING BEARISH",
            "desc":           "Strong downtrend. Use continuation logic.",
            "atr_multiplier": 2.0
        }

    if adx_1d and 18 <= adx_1d < 25:
        return {
            "type":           "weak-trend",
            "tradeable":      True,
            "score":          4,
            "label":          "WEAK TREND",
            "desc":           "ADX developing — reduced confidence. Require stronger sweep/displacement.",
            "atr_multiplier": 1.5
        }

    return {
        "type":           "unknown",
        "tradeable":      False,
        "score":          0,
        "label":          "UNCLEAR",
        "desc":           "Market conditions unclear.",
        "atr_multiplier": 1.5
    }


def assess_btc_stability(btc_data: dict) -> dict:
    if not btc_data:
        return {
            "stable":   False,
            "warnings": ["BTC data unavailable"],
            "score":    0
        }

    warnings = []
    adx = btc_data.get("adx")
    if adx and adx < 18:
        warnings.append("BTC ADX weak — ranging")
    if (btc_data.get("structure", {}).get("struct_bias") == "bear" and
            btc_data.get("trend", {}).get("cls") == "bull"):
        warnings.append("BTC CHoCH detected")

    return {
        "stable":   len(warnings) == 0,
        "warnings": warnings,
        "score":    max(0, 8 - len(warnings) * 3)
    }