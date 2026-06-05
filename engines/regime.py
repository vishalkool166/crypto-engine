def detect_regime(d1d: dict, d4h: dict) -> dict:
    adx_1d = d1d.get("adx")
    adx_4h = d4h.get("adx")
    bb_1d  = d1d.get("bb")
    s20    = d1d.get("slope20")
    s50    = d1d.get("slope50")
    trend  = d1d.get("trend", {})

    # Choppy — hard block
    if (adx_1d is not None and adx_4h is not None
            and adx_1d < 18 and adx_4h < 18):
        return {
            "type": "chop", "tradeable": False, "score": 0,
            "label": "CHOPPY MARKET",
            "desc":  "ADX weak on 1D+4H. No trend."
        }

    # Ranging
    flat = (s20 is not None and abs(s20) < 0.15
            and s50 is not None and abs(s50) < 0.15)
    if (adx_1d is not None and adx_1d < 25
            and bb_1d and bb_1d["width"] < 3 and flat):
        return {
            "type": "ranging", "tradeable": False, "score": 3,
            "label": "RANGING",
            "desc":  "Low ADX + narrow BB + flat EMAs."
        }

    # Volatility expansion
    if (bb_1d and bb_1d["width"] > 8
            and d1d["cur_vol"] > d1d["vol_ma5"] * 1.8):
        return {
            "type": "expansion", "tradeable": True, "score": 7,
            "label": "VOLATILITY EXPANSION",
            "desc":  "BB wide + volume spike. Breakout mode."
        }

    # Trending bull
    if trend.get("cls") == "bull" and adx_1d and adx_1d >= 25:
        return {
            "type": "trending-bull", "tradeable": True, "score": 10,
            "label": "TRENDING BULLISH",
            "desc":  "Strong uptrend. Use continuation logic."
        }

    # Trending bear
    if trend.get("cls") == "bear" and adx_1d and adx_1d >= 25:
        return {
            "type": "trending-bear", "tradeable": True, "score": 10,
            "label": "TRENDING BEARISH",
            "desc":  "Strong downtrend. Use continuation logic."
        }

    # Weak trend
    if adx_1d and 18 <= adx_1d < 25:
        return {
            "type": "weak-trend", "tradeable": False, "score": 4,
            "label": "WEAK TREND",
            "desc":  "ADX developing. Wait for confirmation."
        }

    return {
        "type": "unknown", "tradeable": False, "score": 0,
        "label": "UNCLEAR",
        "desc":  "Market conditions unclear."
    }