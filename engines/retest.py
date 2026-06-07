import pandas as pd


def detect_retest(
    df:           pd.DataFrame,
    d4h:          dict,
    sweep:        dict,
    displacement: dict,
    d1h:          dict = None,
    d1d:          dict = None
) -> dict:

    price  = float(df["close"].iloc[-1])
    atr    = d4h.get("atr") or price * 0.015
    ema20  = d4h.get("ema20")
    ema50  = d4h.get("ema50")
    vol_ma = float(
        pd.Series(
            [c["vol"] for c in d4h.get("last5", [])]
        ).mean()
    ) or 1

    sweep_type = sweep.get("type", "")
    disp_type  = displacement.get("type", "")

    if sweep_type == "bull" and disp_type == "bull":
        trade_dir = "bull"
    elif sweep_type == "bear" and disp_type == "bear":
        trade_dir = "bear"
    elif sweep_type == "bull" and disp_type != "bear":
        trade_dir = "bull"
    elif sweep_type == "bear" and disp_type != "bull":
        trade_dir = "bear"
    elif sweep_type:
        trade_dir = sweep_type
    else:
        trade_dir = disp_type or "bull"

    MIN_WIDTH_PCT = 0.003

    # ── COLLECT FVGs FROM ALL TIMEFRAMES ──
    all_fvgs = []
    for fvg in d4h.get("fvgs", []):
        all_fvgs.append({**fvg, "timeframe": "4h", "priority": 1})
    if d1h:
        for fvg in d1h.get("fvgs", []):
            all_fvgs.append({**fvg, "timeframe": "1h", "priority": 2})
    if d1d:
        for fvg in d1d.get("fvgs", []):
            all_fvgs.append({**fvg, "timeframe": "1d", "priority": 3})

    valid_fvgs = []
    for fvg in all_fvgs:
        if fvg["type"] != trade_dir:
            continue
        width = (fvg["top"] - fvg["bottom"]) / price
        if width < MIN_WIDTH_PCT:
            continue
        if trade_dir == "bear" and fvg["bottom"] < price * 0.97:
            continue
        if trade_dir == "bull" and fvg["top"] > price * 1.03:
            continue
        dist = abs(price - fvg["mid"]) / price
        valid_fvgs.append({**fvg, "width": width, "dist": dist})

    valid_fvgs.sort(key=lambda x: x["dist"])
    matching_fvg = valid_fvgs[0] if valid_fvgs else None

    # ── PREFER OB ZONE OVER FVG ZONE WHEN AVAILABLE ──
    zone      = None
    zone_type = ""

    ob_data    = d4h.get("order_blocks", {})
    nearest_ob = (
        ob_data.get("nearest_bull") if trade_dir == "bull"
        else ob_data.get("nearest_bear")
    )

    ob_zone  = None
    fvg_zone = None

    if nearest_ob and not nearest_ob.get("mitigated"):
        ob_zone = {
            "top":    nearest_ob["top"],
            "bottom": nearest_ob["bottom"],
            "mid":    nearest_ob["mid"]
        }

    if sweep.get("confirmed") and matching_fvg:
        fvg_zone = {
            "top":    matching_fvg["top"],
            "bottom": matching_fvg["bottom"],
            "mid":    matching_fvg["mid"]
        }

    if ob_zone and fvg_zone:
        ob_dist  = abs(price - ob_zone["mid"])  / price
        fvg_dist = abs(price - fvg_zone["mid"]) / price
        if ob_dist <= fvg_dist:
            zone      = ob_zone
            zone_type = "4H Order Block"
        else:
            zone      = fvg_zone
            tf        = matching_fvg.get("timeframe", "4h").upper()
            zone_type = f"{tf} Bullish FVG" if trade_dir == "bull" else f"{tf} Bearish FVG"
    elif ob_zone:
        zone      = ob_zone
        zone_type = "4H Order Block"
    elif fvg_zone:
        zone      = fvg_zone
        tf        = matching_fvg.get("timeframe", "4h").upper()
        zone_type = f"{tf} Bullish FVG" if trade_dir == "bull" else f"{tf} Bearish FVG"
    elif ema20 and abs(price - ema20) / price < 0.04:
        zone      = {"top": ema20 * 1.01, "bottom": ema20 * 0.99, "mid": ema20}
        zone_type = "EMA20 Zone"
    elif ema50 and abs(price - ema50) / price < 0.05:
        zone      = {"top": ema50 * 1.01, "bottom": ema50 * 0.99, "mid": ema50}
        zone_type = "EMA50 Zone"

    if not zone:
        return {
            "status":    "none",
            "label":     "No retest zone",
            "desc":      "No valid OB, FVG or EMA zone found",
            "score":     0,
            "confirmed": False,
            "failed":    False,
            "zone_type": "",
            "zone":      None,
            "trade_dir": trade_dir
        }

    in_zone    = zone["bottom"] <= price <= zone["top"]
    above_zone = price > zone["top"]
    below_zone = price < zone["bottom"]

    recent = df.tail(6)

    def failed_retest():
        if trade_dir == "bull":
            entered     = any(
                c["low"] <= zone["top"] and c["high"] >= zone["bottom"]
                for _, c in recent.iterrows()
            )
            closed_below = any(
                c["close"] < zone["bottom"]
                for _, c in recent.tail(2).iterrows()
            )
            return entered and closed_below
        else:
            entered     = any(
                c["high"] >= zone["bottom"] and c["low"] <= zone["top"]
                for _, c in recent.iterrows()
            )
            closed_above = any(
                c["close"] > zone["top"]
                for _, c in recent.tail(2).iterrows()
            )
            return entered and closed_above

    if failed_retest():
        return {
            "status":    "failed",
            "label":     "Failed Retest",
            "desc":      f"{zone_type} broken — setup invalidated",
            "score":     0,
            "confirmed": False,
            "failed":    True,
            "zone_type": zone_type,
            "zone":      zone,
            "trade_dir": trade_dir
        }

    def rejection_candle():
        for _, c in recent.tail(3).iterrows():
            body = abs(c["close"] - c["open"])
            rng  = c["high"] - c["low"]
            if rng == 0:
                continue
            br = body / rng

            if trade_dir == "bull":
                lw = min(c["open"], c["close"]) - c["low"]
                if (lw / rng > 0.4 and
                        c["close"] > (c["high"] + c["low"]) / 2 and br < 0.5):
                    return {"detected": True, "desc": "Hammer/Pin bar"}
                if (c["close"] > c["open"] and br > 0.6 and
                        c["close"] > zone["mid"]):
                    return {"detected": True, "desc": "Bullish engulfing"}
            else:
                uw = c["high"] - max(c["open"], c["close"])
                if (uw / rng > 0.4 and
                        c["close"] < (c["high"] + c["low"]) / 2 and br < 0.5):
                    return {"detected": True, "desc": "Shooting star"}
                if (c["close"] < c["open"] and br > 0.6 and
                        c["close"] < zone["mid"]):
                    return {"detected": True, "desc": "Bearish engulfing"}

        return {"detected": False}

    rejection  = rejection_candle()
    avg_vol    = float(recent["volume"].mean())
    absorption = avg_vol < vol_ma * 0.8
    vol_ok     = float(recent["volume"].iloc[-1]) > vol_ma * 0.8

    if in_zone and rejection["detected"] and (absorption or vol_ok):
        return {
            "status":    "confirmed",
            "label":     "Retest Confirmed",
            "desc":      f"{zone_type} held · {rejection['desc']}",
            "score":     12,
            "confirmed": True,
            "failed":    False,
            "zone_type": zone_type,
            "zone":      zone,
            "rejection": rejection,
            "absorption": absorption,
            "trade_dir": trade_dir
        }

    if in_zone and rejection["detected"]:
        return {
            "status":    "partial",
            "label":     "Partial Retest",
            "desc":      f"{zone_type} — rejection present, awaiting volume",
            "score":     9,
            "confirmed": False,
            "failed":    False,
            "zone_type": zone_type,
            "zone":      zone,
            "rejection": rejection,
            "trade_dir": trade_dir
        }

    if in_zone:
        return {
            "status":    "pending",
            "label":     "In Retest Zone",
            "desc":      f"Inside {zone_type} — waiting for rejection",
            "score":     5,
            "confirmed": False,
            "failed":    False,
            "zone_type": zone_type,
            "zone":      zone,
            "trade_dir": trade_dir
        }

    if trade_dir == "bull" and above_zone:
        return {
            "status":    "missed",
            "label":     "Above Zone — Entry Missed",
            "desc":      f"Price above {zone_type}",
            "score":     0,
            "confirmed": False,
            "failed":    False,
            "zone_type": zone_type,
            "zone":      zone,
            "trade_dir": trade_dir
        }

    if trade_dir == "bear" and below_zone:
        return {
            "status":    "missed",
            "label":     "Below Zone — Entry Missed",
            "desc":      f"Price below {zone_type}",
            "score":     0,
            "confirmed": False,
            "failed":    False,
            "zone_type": zone_type,
            "zone":      zone,
            "trade_dir": trade_dir
        }

    return {
        "status":    "approaching",
        "label":     "Approaching Zone",
        "desc":      f"Price approaching {zone_type} at {zone['mid']:.4f}",
        "score":     3,
        "confirmed": False,
        "failed":    False,
        "zone_type": zone_type,
        "zone":      zone,
        "trade_dir": trade_dir
    }