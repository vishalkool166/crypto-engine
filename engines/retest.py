import pandas as pd

def detect_retest(
    df: pd.DataFrame,
    d4h: dict,
    sweep: dict,
    displacement: dict
) -> dict:

    price = float(df["close"].iloc[-1])
    atr   = d4h.get("atr") or price * 0.015
    fvgs  = d4h.get("fvgs", [])
    ema20 = d4h.get("ema20")
    ema50 = d4h.get("ema50")
    vol_ma = float(
        pd.Series([c["vol"] for c in d4h.get("last5", [])]).mean()
    ) or 1

    # ── DETERMINE TRADE DIRECTION ──
    # Must match sweep + displacement
    # Both must agree — if conflict use sweep
    sweep_type = sweep.get("type", "")
    disp_type  = displacement.get("type", "")

    # Determine dominant direction
    if sweep_type == "bull" and disp_type == "bull":
        trade_dir = "bull"
    elif sweep_type == "bear" and disp_type == "bear":
        trade_dir = "bear"
    elif sweep_type == "bull" and disp_type != "bear":
        trade_dir = "bull"
    elif sweep_type == "bear" and disp_type != "bull":
        trade_dir = "bear"
    elif sweep_type:
        # fallback to sweep direction
        trade_dir = sweep_type
    else:
        trade_dir = disp_type or "bull"

    # ── FIND MATCHING FVG FOR DIRECTION ──
    # Only use FVG that matches trade direction
    # Bull trade = look for bullish FVG to retest
    # Bear trade = look for bearish FVG to retest
    matching_fvg = next(
        (f for f in fvgs if f["type"] == trade_dir),
        None
    )

    # ── BUILD RETEST ZONE ──
    zone      = None
    zone_type = ""

    if sweep.get("confirmed") and matching_fvg:
        zone = {
            "top":    matching_fvg["top"],
            "bottom": matching_fvg["bottom"],
            "mid":    matching_fvg["mid"]
        }
        zone_type = (
            "Bullish FVG" if trade_dir == "bull"
            else "Bearish FVG"
        )

    elif ema20 and abs(price - ema20) / price < 0.025:
        zone = {
            "top":    ema20 * 1.005,
            "bottom": ema20 * 0.995,
            "mid":    ema20
        }
        zone_type = "EMA20 Zone"

    elif ema50 and abs(price - ema50) / price < 0.03:
        zone = {
            "top":    ema50 * 1.005,
            "bottom": ema50 * 0.995,
            "mid":    ema50
        }
        zone_type = "EMA50 Zone"

    if not zone:
        return {
            "status":    "none",
            "label":     "No retest zone",
            "desc":      "Wait for price to return to FVG or EMA",
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

    # ── FAILED RETEST CHECK ──
    # Direction aware — bull trade failing means
    # price closed below bull FVG bottom
    # bear trade failing means price closed
    # above bear FVG top
    def failed_retest():
        if trade_dir == "bull":
            entered = any(
                c["low"] <= zone["top"] and
                c["high"] >= zone["bottom"]
                for _, c in recent.iterrows()
            )
            closed_below = any(
                c["close"] < zone["bottom"]
                for _, c in recent.tail(2).iterrows()
            )
            return entered and closed_below
        else:
            entered = any(
                c["high"] >= zone["bottom"] and
                c["low"] <= zone["top"]
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

    # ── REJECTION CANDLE CHECK ──
    # Direction aware
    def rejection_candle():
        for _, c in recent.tail(3).iterrows():
            body = abs(c["close"] - c["open"])
            rng  = c["high"] - c["low"]
            if rng == 0:
                continue
            br = body / rng

            if trade_dir == "bull":
                # Looking for bullish rejection
                # hammer, pin bar, bullish engulf
                lw = min(
                    c["open"], c["close"]
                ) - c["low"]
                if (
                    lw / rng > 0.4 and
                    c["close"] > (
                        c["high"] + c["low"]
                    ) / 2 and
                    br < 0.5
                ):
                    return {
                        "detected": True,
                        "desc":     "Hammer/Pin bar"
                    }
                if (
                    c["close"] > c["open"] and
                    br > 0.6 and
                    c["close"] > zone["mid"]
                ):
                    return {
                        "detected": True,
                        "desc":     "Bullish engulfing"
                    }
            else:
                # Looking for bearish rejection
                # shooting star, bearish engulf
                uw = c["high"] - max(
                    c["open"], c["close"]
                )
                if (
                    uw / rng > 0.4 and
                    c["close"] < (
                        c["high"] + c["low"]
                    ) / 2 and
                    br < 0.5
                ):
                    return {
                        "detected": True,
                        "desc":     "Shooting star"
                    }
                if (
                    c["close"] < c["open"] and
                    br > 0.6 and
                    c["close"] < zone["mid"]
                ):
                    return {
                        "detected": True,
                        "desc":     "Bearish engulfing"
                    }

        return {"detected": False}

    rejection  = rejection_candle()
    avg_vol    = float(recent["volume"].mean())
    absorption = avg_vol < vol_ma * 0.8
    vol_ok     = float(
        recent["volume"].iloc[-1]
    ) > vol_ma * 0.8

    # ── CONFIRMED RETEST ──
    if in_zone and rejection["detected"] and (
        absorption or vol_ok
    ):
        return {
            "status":    "confirmed",
            "label":     "Retest Confirmed",
            "desc": (
                f"{zone_type} held · "
                f"{rejection['desc']}"
            ),
            "score":     12,
            "confirmed": True,
            "failed":    False,
            "zone_type": zone_type,
            "zone":      zone,
            "rejection": rejection,
            "absorption": absorption,
            "trade_dir": trade_dir
        }

    # ── PARTIAL RETEST ──
    if in_zone and rejection["detected"]:
        return {
            "status":    "partial",
            "label":     "Partial Retest",
            "desc": (
                f"{zone_type} — rejection present, "
                f"awaiting volume"
            ),
            "score":     9,
            "confirmed": False,
            "failed":    False,
            "zone_type": zone_type,
            "zone":      zone,
            "rejection": rejection,
            "trade_dir": trade_dir
        }

    # ── IN ZONE — WAITING ──
    if in_zone:
        return {
            "status":    "pending",
            "label":     "In Retest Zone",
            "desc": (
                f"Inside {zone_type} — "
                f"waiting for rejection"
            ),
            "score":     5,
            "confirmed": False,
            "failed":    False,
            "zone_type": zone_type,
            "zone":      zone,
            "trade_dir": trade_dir
        }

    # ── ABOVE ZONE — BULL MISSED ──
    if trade_dir == "bull" and above_zone:
        return {
            "status":    "missed",
            "label":     "Above Zone — Entry Missed",
            "desc":      f"Price above {zone_type}",
            "score":     2,
            "confirmed": False,
            "failed":    False,
            "zone_type": zone_type,
            "zone":      zone,
            "trade_dir": trade_dir
        }

    # ── BELOW ZONE — BEAR MISSED ──
    if trade_dir == "bear" and below_zone:
        return {
            "status":    "missed",
            "label":     "Below Zone — Entry Missed",
            "desc":      f"Price below {zone_type}",
            "score":     2,
            "confirmed": False,
            "failed":    False,
            "zone_type": zone_type,
            "zone":      zone,
            "trade_dir": trade_dir
        }

    # ── APPROACHING ──
    return {
        "status":    "approaching",
        "label":     "Approaching Zone",
        "desc": (
            f"Price approaching {zone_type} "
            f"at {zone['mid']:.2f}"
        ),
        "score":     3,
        "confirmed": False,
        "failed":    False,
        "zone_type": zone_type,
        "zone":      zone,
        "trade_dir": trade_dir
    }