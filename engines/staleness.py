from config import cfg


REGIME_CANDLE_LIMITS = {
    "trending-bull": 10,
    "trending-bear": 10,
    "expansion":     6,
    "weak-trend":    15,
    "ranging":       20,
    "chop":          0,
    "unknown":       10,
}

COMPONENT_WEIGHTS = {
    "sweep":        1.0,
    "displacement": 0.8,
    "retest":       1.2,
}


def _atr_candle_limit(atr: float, price: float, base_limit: int) -> int:
    if price <= 0:
        return base_limit
    atr_pct = atr / price * 100
    if atr_pct > 4.0:
        return max(4, round(base_limit * 0.6))
    if atr_pct > 2.0:
        return max(5, round(base_limit * 0.8))
    if atr_pct < 0.5:
        return round(base_limit * 1.5)
    return base_limit


def check_sweep_staleness(
    sweep:   dict,
    regime:  dict,
    atr:     float,
    price:   float
) -> dict:
    if not sweep.get("detected"):
        return {
            "stale":       False,
            "reason":      "No sweep detected",
            "candles_ago": 0,
            "limit":       0,
            "component":   "sweep"
        }

    candles_ago  = sweep.get("candles_ago", 0)
    regime_type  = regime.get("type", "unknown")
    base_limit   = REGIME_CANDLE_LIMITS.get(regime_type, 10)
    weight       = COMPONENT_WEIGHTS["sweep"]
    adj_limit    = _atr_candle_limit(atr, price, base_limit)
    final_limit  = round(adj_limit * weight)

    stale = candles_ago > final_limit

    return {
        "stale":       stale,
        "reason":      f"Sweep {candles_ago} candles ago — limit {final_limit}" if stale else "",
        "candles_ago": candles_ago,
        "limit":       final_limit,
        "component":   "sweep"
    }


def check_displacement_staleness(
    displacement: dict,
    regime:       dict,
    atr:          float,
    price:        float
) -> dict:
    if not displacement.get("confirmed"):
        return {
            "stale":       False,
            "reason":      "No displacement confirmed",
            "candles_ago": 0,
            "limit":       0,
            "component":   "displacement"
        }

    items        = displacement.get("items", [])
    candles_ago  = len(items)

    regime_type  = regime.get("type", "unknown")
    base_limit   = REGIME_CANDLE_LIMITS.get(regime_type, 10)
    weight       = COMPONENT_WEIGHTS["displacement"]
    adj_limit    = _atr_candle_limit(atr, price, base_limit)
    final_limit  = round(adj_limit * weight)

    stale = candles_ago > final_limit

    return {
        "stale":       stale,
        "reason":      f"Displacement {candles_ago} candles ago — limit {final_limit}" if stale else "",
        "candles_ago": candles_ago,
        "limit":       final_limit,
        "component":   "displacement"
    }


def check_retest_staleness(
    retest:  dict,
    regime:  dict,
    atr:     float,
    price:   float
) -> dict:
    status = retest.get("status", "none")

    if status in ("none", "missed", "failed"):
        return {
            "stale":       True,
            "reason":      f"Retest status: {status}",
            "candles_ago": 0,
            "limit":       0,
            "component":   "retest"
        }

    regime_type  = regime.get("type", "unknown")
    base_limit   = REGIME_CANDLE_LIMITS.get(regime_type, 10)
    weight       = COMPONENT_WEIGHTS["retest"]
    adj_limit    = _atr_candle_limit(atr, price, base_limit)
    final_limit  = round(adj_limit * weight)

    return {
        "stale":       False,
        "reason":      "",
        "candles_ago": 0,
        "limit":       final_limit,
        "component":   "retest"
    }


def assess_setup_staleness(
    sweep:        dict,
    displacement: dict,
    retest:       dict,
    regime:       dict,
    atr:          float,
    price:        float
) -> dict:

    sweep_check  = check_sweep_staleness(sweep, regime, atr, price)
    disp_check   = check_displacement_staleness(displacement, regime, atr, price)
    retest_check = check_retest_staleness(retest, regime, atr, price)

    checks = [sweep_check, disp_check, retest_check]

    sweep_stale = sweep_check["stale"]
    disp_stale  = disp_check["stale"]
    retest_stale = retest_check["stale"]

    stale_reasons = [c["reason"] for c in checks if c["stale"] and c["reason"]]

    if sweep_stale and disp_stale:
        overall = "EXPIRED"
    elif sweep_stale or disp_stale:
        overall = "DEGRADED"
    elif retest_stale:
        overall = "DEGRADED"
    else:
        overall = "FRESH"

    return {
        "overall":      overall,
        "fresh":        overall == "FRESH",
        "degraded":     overall == "DEGRADED",
        "expired":      overall == "EXPIRED",
        "reasons":      stale_reasons,
        "sweep":        sweep_check,
        "displacement": disp_check,
        "retest":       retest_check,
        "tradeable":    overall in ("FRESH", "DEGRADED"),
        "score_mult":   1.0 if overall == "FRESH" else 0.85 if overall == "DEGRADED" else 0.6
    }