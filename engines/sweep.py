import pandas as pd
from config import cfg

TF_CANDLE_HOURS = {
    "15m": 0.25,
    "1h":  1.0,
    "4h":  4.0,
    "1d":  24.0,
    "1w":  168.0
}


def detect(
    df_1h:     pd.DataFrame,
    d1h:       dict,
    direction: str,
    timeframe: str = "1h"
) -> dict:

    atr    = d1h.get("atr") or float(df_1h["close"].iloc[-1]) * 0.01
    swings = d1h.get("swings", {})
    price  = float(df_1h["close"].iloc[-1])
    vol_ma = float(df_1h["volume"].rolling(20).mean().iloc[-1]) or 1

    SE               = cfg.SCALP_ENGINE
    hours_per_candle = TF_CANDLE_HOURS.get(timeframe, 1.0)
    max_age_hours    = SE["sweep_max_age_hours"]
    lookback         = int(max_age_hours / hours_per_candle) + 5
    min_wick_atr     = SE["sweep_min_wick_atr"]

    results = []

    def relevance(candles_ago: int) -> dict:
        age_hours = candles_ago * hours_per_candle
        if age_hours <= max_age_hours * 0.25:
            return {"label": "HIGH",    "pts": 12, "mult": 1.0}
        if age_hours <= max_age_hours * 0.50:
            return {"label": "MEDIUM",  "pts": 8,  "mult": 0.67}
        if age_hours <= max_age_hours * 0.75:
            return {"label": "LOW",     "pts": 4,  "mult": 0.33}
        if age_hours <= max_age_hours:
            return {"label": "STALE",   "pts": 2,  "mult": 0.15}
        return     {"label": "EXPIRED", "pts": 0,  "mult": 0.0}

    def check_below(level, label, base_strength):
        if not level or level <= 0:
            return None
        sl = df_1h.tail(lookback)
        for i in range(len(sl) - 1):
            c = sl.iloc[i]
            if float(c["low"]) < level and float(c["close"]) > level:
                candles_ago = len(sl) - 1 - i
                rel         = relevance(candles_ago)
                if rel["mult"] == 0:
                    continue
                wick = level - float(c["low"])
                if wick < atr * min_wick_atr:
                    continue
                vs         = float(c["volume"]) / vol_ma
                body_below = min(float(c["open"]), float(c["close"])) < level
                intensity  = min(10,
                    (3 if wick / atr > 0.5 else 1) +
                    (3 if vs > 1.5 else 1 if vs > 1.0 else 0) +
                    2 +
                    (2 if not body_below else 0)
                )
                confirmed   = bool(float(c["close"]) > level and price > level)
                adj_score   = round(rel["pts"] * (intensity / 10))
                return {
                    "type":        "bull",
                    "label":       label,
                    "level":       float(level),
                    "sweep_low":   float(c["low"]),
                    "sweep_high":  None,
                    "wick":        round(wick, 6),
                    "wick_atr":    round(wick / atr, 2),
                    "magnitude":   round(wick / atr, 2),
                    "vol_ratio":   round(vs, 2),
                    "vol_spike":   round(vs, 2),
                    "intensity":   intensity,
                    "confirmed":   confirmed,
                    "candles_ago": candles_ago,
                    "age_hours":   round(candles_ago * hours_per_candle, 1),
                    "relevance":   rel,
                    "score":       adj_score if confirmed else round(adj_score * 0.4),
                    "level_type":  label.lower().replace(" sweep", "").replace(" ", "_"),
                    "level_label": label,
                    "priority":    1 if "weekly" in label.lower() else 2,
                }
        return None

    def check_above(level, label, base_strength):
        if not level or level <= 0:
            return None
        sl = df_1h.tail(lookback)
        for i in range(len(sl) - 1):
            c = sl.iloc[i]
            if float(c["high"]) > level and float(c["close"]) < level:
                candles_ago = len(sl) - 1 - i
                rel         = relevance(candles_ago)
                if rel["mult"] == 0:
                    continue
                wick = float(c["high"]) - level
                if wick < atr * min_wick_atr:
                    continue
                vs         = float(c["volume"]) / vol_ma
                body_above = max(float(c["open"]), float(c["close"])) > level
                intensity  = min(10,
                    (3 if wick / atr > 0.5 else 1) +
                    (3 if vs > 1.5 else 1 if vs > 1.0 else 0) +
                    2 +
                    (2 if not body_above else 0)
                )
                confirmed   = bool(float(c["close"]) < level and price < level)
                adj_score   = round(rel["pts"] * (intensity / 10))
                return {
                    "type":        "bear",
                    "label":       label,
                    "level":       float(level),
                    "sweep_low":   None,
                    "sweep_high":  float(c["high"]),
                    "wick":        round(wick, 6),
                    "wick_atr":    round(wick / atr, 2),
                    "magnitude":   round(wick / atr, 2),
                    "vol_ratio":   round(vs, 2),
                    "vol_spike":   round(vs, 2),
                    "intensity":   intensity,
                    "confirmed":   confirmed,
                    "candles_ago": candles_ago,
                    "age_hours":   round(candles_ago * hours_per_candle, 1),
                    "relevance":   rel,
                    "score":       adj_score if confirmed else round(adj_score * 0.4),
                    "level_type":  label.lower().replace(" sweep", "").replace(" ", "_"),
                    "level_label": label,
                    "priority":    1 if "weekly" in label.lower() else 2,
                }
        return None

    key_levels = {
        "pdl": float(df_1h.iloc[-2]["low"])  if len(df_1h) >= 2 else 0,
        "pdh": float(df_1h.iloc[-2]["high"]) if len(df_1h) >= 2 else 0,
        "pwl": 0,
        "pwh": 0,
    }

    if direction == "LONG":
        checks = [
            (check_below, swings["last_low"]["price"]  if swings.get("last_low")  else None, "Swing Low Sweep",   7),
            (check_below, swings["prev_low"]["price"]  if swings.get("prev_low")  else None, "Prev Low Sweep",    6),
            (check_below, key_levels["pdl"],                                                  "PDL Sweep",         8),
            (check_below, key_levels["pwl"],                                                  "Weekly Low Sweep",  10),
        ]
    else:
        checks = [
            (check_above, swings["last_high"]["price"] if swings.get("last_high") else None, "Swing High Sweep",  7),
            (check_above, swings["prev_high"]["price"] if swings.get("prev_high") else None, "Prev High Sweep",   6),
            (check_above, key_levels["pdh"],                                                  "PDH Sweep",         8),
            (check_above, key_levels["pwh"],                                                  "Weekly High Sweep", 10),
        ]

    for fn, level, label, strength in checks:
        res = fn(level, label, strength)
        if res and res["intensity"] >= 3:
            results.append(res)

    if not results:
        return {
            "detected":   False,
            "confirmed":  False,
            "score":      0.0,
            "items":      [],
            "label":      "No sweep detected",
            "desc":       "No confirmed liquidity grab on key levels",
            "sweep_low":  None,
            "sweep_high": None,
            "sweep":      None,
        }

    results.sort(key=lambda x: x["score"], reverse=True)
    best      = results[0]
    confirmed = any(r["confirmed"] for r in results)

    base_score = best["score"] / 12.0
    base_score = min(base_score, 1.0)

    return {
        "detected":   True,
        "confirmed":  confirmed,
        "score":      round(base_score, 3),
        "type":       best["type"],
        "label":      best["label"],
        "level":      best["level"],
        "intensity":  best["intensity"],
        "magnitude":  best["magnitude"],
        "vol_spike":  best["vol_spike"],
        "vol_ratio":  best["vol_ratio"],
        "candles_ago":best["candles_ago"],
        "age_hours":  best["age_hours"],
        "relevance":  best["relevance"],
        "items":      results,
        "sweep_low":  best.get("sweep_low"),
        "sweep_high": best.get("sweep_high"),
        "sweep":      best,
        "desc":       f"Level: {best['level']:.4f} — {best['relevance']['label']} ({best['age_hours']:.1f}h ago)",
        "all_sweeps": results,
    }


detect_sweep = detect