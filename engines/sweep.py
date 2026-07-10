import pandas as pd


TF_CANDLE_HOURS = {
    "15m": 0.25,
    "1h":  1.0,
    "4h":  4.0,
    "1d":  24.0,
    "1w":  168.0
}


def detect_sweep(
    df:         pd.DataFrame,
    key_levels: dict,
    atr:        float,
    swings:     dict,
    timeframe:  str = "4h"
) -> dict:

    price  = float(df["close"].iloc[-1])
    vol_ma = float(df["volume"].rolling(10).mean().iloc[-1]) or 1
    results = []

    atr_pct          = (atr / price) if price > 0 else 0.015
    hours_per_candle = TF_CANDLE_HOURS.get(timeframe, 4.0)

    def relevance(candles_ago: int) -> dict:
        age_hours = candles_ago * hours_per_candle

        if age_hours <= 12:
            return {"label": "HIGH",    "pts": 12, "mult": 1.0}
        if age_hours <= 48:
            return {"label": "MEDIUM",  "pts": 8,  "mult": 0.67}
        if age_hours <= 120:
            return {"label": "LOW",     "pts": 4,  "mult": 0.33}
        return     {"label": "EXPIRED", "pts": 0,  "mult": 0.0}

    def check_below(level, label, base_strength, lookback=20):
        if not level or level <= 0:
            return None
        sl = df.tail(lookback)
        for i in range(len(sl) - 1):
            c = sl.iloc[i]
            if c["low"] < level and c["close"] > level:
                candles_ago = len(sl) - 1 - i
                rel         = relevance(candles_ago)
                if rel["mult"] == 0:
                    continue

                mag        = (level - c["low"]) / atr if atr > 0 else 0
                vs         = c["volume"] / vol_ma
                body_below = min(c["open"], c["close"]) < level

                intensity = min(10,
                    (3 if mag > 0.5 else 1) +
                    (3 if vs > 1.5 else 1 if vs > 1.0 else 0) +
                    2 +
                    (2 if not body_below else 0)
                )

                close_confirmed = bool(c["close"] > level)
                price_confirmed = bool(price > level)
                confirmed       = close_confirmed and price_confirmed

                adj_score = round(rel["pts"] * (intensity / 10))

                return {
                    "type":        "bull",
                    "label":       label,
                    "level":       float(level),
                    "sweep_low":   float(c["low"]),
                    "sweep_high":  None,
                    "magnitude":   round(mag, 2),
                    "vol_spike":   round(vs, 2),
                    "intensity":   intensity,
                    "confirmed":   confirmed,
                    "candles_ago": candles_ago,
                    "age_hours":   round(candles_ago * hours_per_candle, 1),
                    "relevance":   rel,
                    "score":       adj_score if confirmed else round(adj_score * 0.4)
                }
        return None

    def check_above(level, label, base_strength, lookback=20):
        if not level or level <= 0:
            return None
        sl = df.tail(lookback)
        for i in range(len(sl) - 1):
            c = sl.iloc[i]
            if c["high"] > level and c["close"] < level:
                candles_ago = len(sl) - 1 - i
                rel         = relevance(candles_ago)
                if rel["mult"] == 0:
                    continue

                mag        = (c["high"] - level) / atr if atr > 0 else 0
                vs         = c["volume"] / vol_ma
                body_above = max(c["open"], c["close"]) > level

                intensity = min(10,
                    (3 if mag > 0.5 else 1) +
                    (3 if vs > 1.5 else 1 if vs > 1.0 else 0) +
                    2 +
                    (2 if not body_above else 0)
                )

                close_confirmed = bool(c["close"] < level)
                price_confirmed = bool(price < level)
                confirmed       = close_confirmed and price_confirmed

                adj_score = round(rel["pts"] * (intensity / 10))

                return {
                    "type":        "bear",
                    "label":       label,
                    "level":       float(level),
                    "sweep_low":   None,
                    "sweep_high":  float(c["high"]),
                    "magnitude":   round(mag, 2),
                    "vol_spike":   round(vs, 2),
                    "intensity":   intensity,
                    "confirmed":   confirmed,
                    "candles_ago": candles_ago,
                    "age_hours":   round(candles_ago * hours_per_candle, 1),
                    "relevance":   rel,
                    "score":       adj_score if confirmed else round(adj_score * 0.4)
                }
        return None

    checks = [
        (check_below, key_levels.get("pdl"),                                         "PDL Sweep",         8),
        (check_above, key_levels.get("pdh"),                                         "PDH Sweep",         8),
        (check_below, swings["last_low"]["price"]  if swings["last_low"]  else None, "Swing Low Sweep",   7),
        (check_above, swings["last_high"]["price"] if swings["last_high"] else None, "Swing High Sweep",  7),
        (check_below, key_levels.get("pwl"),                                         "Weekly Low Sweep",  10),
        (check_above, key_levels.get("pwh"),                                         "Weekly High Sweep", 10),
    ]

    for fn, level, label, strength in checks:
        res = fn(level, label, strength)
        if res and res["intensity"] >= 3:
            results.append(res)

    if not results:
        return {
            "detected":   False,
            "confirmed":  False,
            "score":      0,
            "items":      [],
            "label":      "No sweep detected",
            "desc":       "No confirmed liquidity grab on key levels",
            "sweep_low":  None,
            "sweep_high": None
        }

    results.sort(key=lambda x: x["score"], reverse=True)
    best      = results[0]
    confirmed = any(r["confirmed"] for r in results)

    return {
        "detected":    True,
        "confirmed":   confirmed,
        "type":        best["type"],
        "label":       best["label"],
        "level":       best["level"],
        "intensity":   best["intensity"],
        "magnitude":   best["magnitude"],
        "vol_spike":   best["vol_spike"],
        "candles_ago": best["candles_ago"],
        "age_hours":   best.get("age_hours", 0),
        "relevance":   best["relevance"],
        "score":       best["score"],
        "items":       results,
        "sweep_low":   best.get("sweep_low"),
        "sweep_high":  best.get("sweep_high"),
        "desc":        f"Level: {best['level']:.4f} — {best['relevance']['label']} ({best.get('age_hours', 0):.1f}h ago)"
    }