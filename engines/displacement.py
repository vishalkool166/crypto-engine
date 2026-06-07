import pandas as pd


def detect_displacement(
    df:  pd.DataFrame,
    atr: float
) -> dict:

    if not atr or len(df) < 10:
        return {
            "confirmed": False,
            "score":     0,
            "label":     "No displacement",
            "desc":      "Not enough data",
            "items":     []
        }

    recent = df.tail(8)
    vol_ma = float(df["volume"].rolling(10).mean().iloc[-1]) or 1
    disps  = []

    for i in range(1, len(recent)):
        c    = recent.iloc[i]
        prev = recent.iloc[i - 1]
        body = abs(c["close"] - c["open"])
        rng  = c["high"] - c["low"]
        bull = c["close"] > c["open"]

        if rng == 0:
            continue

        re = rng > atr * 1.5
        sb = body / rng > 0.6
        bp = (
            c["close"] > prev["high"] if bull
            else c["close"] < prev["low"]
        )
        vs = c["volume"] / vol_ma
        vc = bool(vs > 1.2)

        if re and sb and bp:
            disps.append({
                "direction":   "bull" if bull else "bear",
                "range_mult":  round(rng / atr, 2),
                "body_pct":    round(body / rng * 100),
                "vol_spike":   round(vs, 2),
                "vol_confirm": vc,
                "moderate":    False,
                "weak":        False,
                "label": (
                    "Bullish Displacement" if bull
                    else "Bearish Displacement"
                ),
                "score": 11 if vc else 8
            })

        elif rng > atr * 1.2 and body / rng > 0.5:
            disps.append({
                "direction":   "bull" if bull else "bear",
                "range_mult":  round(rng / atr, 2),
                "body_pct":    round(body / rng * 100),
                "vol_spike":   round(vs, 2),
                "vol_confirm": vc,
                "moderate":    True,
                "weak":        False,
                "label": (
                    "Moderate Bull Move" if bull
                    else "Moderate Bear Move"
                ),
                "score": 7
            })

        elif rng > atr * 0.8 and body / rng > 0.4:
            disps.append({
                "direction":   "bull" if bull else "bear",
                "range_mult":  round(rng / atr, 2),
                "body_pct":    round(body / rng * 100),
                "vol_spike":   round(vs, 2),
                "vol_confirm": vc,
                "moderate":    True,
                "weak":        True,
                "label": (
                    "Weak Bull Move" if bull
                    else "Weak Bear Move"
                ),
                "score": 3
            })

    if not disps:
        return {
            "confirmed": False,
            "score":     0,
            "label":     "No displacement",
            "desc":      "No impulsive move found",
            "items":     []
        }

    disps_sorted = sorted(disps, key=lambda x: x["score"], reverse=True)
    best         = disps_sorted[0]
    latest       = disps[-1]

    bull_disps = [d for d in disps if d["direction"] == "bull"]
    bear_disps = [d for d in disps if d["direction"] == "bear"]

    if len(bull_disps) > len(bear_disps):
        consensus_dir = "bull"
    elif len(bear_disps) > len(bull_disps):
        consensus_dir = "bear"
    else:
        consensus_dir = best["direction"]

    if consensus_dir == "bull":
        consensus_label = (
            "Moderate Bull Move"    if best["moderate"] and not best["weak"] else
            "Weak Bull Move"        if best["weak"] else
            "Bullish Displacement"
        )
    else:
        consensus_label = (
            "Moderate Bear Move"    if best["moderate"] and not best["weak"] else
            "Weak Bear Move"        if best["weak"] else
            "Bearish Displacement"
        )

    final_score = best["score"]

    # Recency bonus — latest candle confirms consensus
    if latest["direction"] == consensus_dir:
        final_score = min(11, final_score + 1)

    # Recency penalty — latest candle contradicts consensus
    # and is nearly as strong as the best
    if (
        latest["direction"] != consensus_dir and
        latest["score"] >= best["score"] * 0.8
    ):
        final_score = max(0, final_score - 2)

    return {
        "confirmed":   True,
        "strong":      not best["moderate"],
        "moderate":    best["moderate"] and not best["weak"],
        "weak":        best.get("weak", False),
        "type":        consensus_dir,
        "label":       consensus_label,
        "range_mult":  best["range_mult"],
        "body_pct":    best["body_pct"],
        "vol_spike":   best["vol_spike"],
        "vol_confirm": bool(best["vol_confirm"]),
        "score":       final_score,
        "latest": {**latest, "vol_confirm": bool(latest["vol_confirm"])},
        "best":   {**best,   "vol_confirm": bool(best["vol_confirm"])},
        "items":  [{**d,     "vol_confirm": bool(d["vol_confirm"])} for d in disps],
        "desc": (
            f"Range {best['range_mult']}x ATR · "
            f"Body {best['body_pct']}% · "
            f"Vol {best['vol_spike']}x · "
            f"Consensus: {consensus_dir}"
        )
    }