import logging
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional
from config import cfg

log = logging.getLogger(__name__)

HE = cfg.HYBRID_ENGINE

TF_CANDLE_HOURS = {
    "15m": 0.25,
    "1h":  1.0,
    "4h":  4.0,
    "1d":  24.0,
    "1w":  168.0,
}


@dataclass
class SweepLevel:
    type:        str
    label:       str
    level:       float
    sweep_low:   Optional[float]
    sweep_high:  Optional[float]
    wick:        float
    wick_atr:    float
    vol_ratio:   float
    intensity:   int
    confirmed:   bool
    candles_ago: int
    age_hours:   float
    score:       float
    priority:    int
    displacement: dict = field(default_factory=dict)


@dataclass
class SweepResult:
    detected:    bool
    confirmed:   bool
    score:       float
    sweep:       Optional[SweepLevel]
    all_sweeps:  list
    displacement: dict
    label:       str
    desc:        str


def detect(
    df_1h:     pd.DataFrame,
    d1h:       dict,
    direction: str,
    timeframe: str = "1h",
) -> SweepResult:
    atr    = float(d1h.get("atr") or df_1h["close"].iloc[-1] * 0.01)
    swings = d1h.get("swings", {})
    price  = float(df_1h["close"].iloc[-1])
    vol_ma = float(df_1h["volume"].rolling(20).mean().iloc[-1]) or 1.0

    hours_per_candle = TF_CANDLE_HOURS.get(timeframe, 1.0)
    max_age_hours    = HE["sweep_max_age_hours"]
    lookback         = int(max_age_hours / hours_per_candle) + 5
    min_wick_atr     = HE["sweep_min_wick_atr"]

    key_levels = _build_key_levels(df_1h, swings)
    results    = []

    if direction == "LONG":
        checks = [
            (swings.get("last_low",  {}).get("price"), "Swing Low Sweep",    7),
            (swings.get("prev_low",  {}).get("price"), "Prev Low Sweep",     6),
            (key_levels.get("pdl"),                    "PDL Sweep",          8),
            (key_levels.get("pwl"),                    "Weekly Low Sweep",  10),
        ]
        for level, label, strength in checks:
            result = _check_below(
                df_1h, level, label, atr, vol_ma,
                lookback, hours_per_candle, min_wick_atr, price,
            )
            if result:
                results.append(result)
    else:
        checks = [
            (swings.get("last_high", {}).get("price"), "Swing High Sweep",   7),
            (swings.get("prev_high", {}).get("price"), "Prev High Sweep",    6),
            (key_levels.get("pdh"),                    "PDH Sweep",          8),
            (key_levels.get("pwh"),                    "Weekly High Sweep", 10),
        ]
        for level, label, strength in checks:
            result = _check_above(
                df_1h, level, label, atr, vol_ma,
                lookback, hours_per_candle, min_wick_atr, price,
            )
            if result:
                results.append(result)

    if not results:
        return SweepResult(
            detected     = False,
            confirmed    = False,
            score        = 0.0,
            sweep        = None,
            all_sweeps   = [],
            displacement = {"found": False, "score": 0.0},
            label        = "No sweep detected",
            desc         = "No confirmed liquidity grab on key levels",
        )

    results.sort(key=lambda x: x.score, reverse=True)
    best      = results[0]
    confirmed = any(r.confirmed for r in results)
    base_score = min(best.score / 12.0, 1.0)

    return SweepResult(
        detected     = True,
        confirmed    = confirmed,
        score        = round(base_score, 3),
        sweep        = best,
        all_sweeps   = results,
        displacement = best.displacement,
        label        = best.label,
        desc         = (
            f"Level:{best.level:.4f} "
            f"{_relevance_label(best.age_hours, max_age_hours)} "
            f"({best.age_hours:.1f}h ago)"
            + (" +displacement" if best.displacement.get("found") else "")
        ),
    )


def _build_key_levels(df_1h: pd.DataFrame, swings: dict) -> dict:
    levels = {
        "pdl": 0.0,
        "pdh": 0.0,
        "pwl": 0.0,
        "pwh": 0.0,
    }

    if len(df_1h) >= 2:
        levels["pdl"] = float(df_1h.iloc[-2]["low"])
        levels["pdh"] = float(df_1h.iloc[-2]["high"])

    try:
        from data.store import load_candles
        df_1w = load_candles("BTC", "1w", limit=5)
        if df_1w is not None and len(df_1w) >= 2:
            levels["pwl"] = float(df_1w.iloc[-2]["low"])
            levels["pwh"] = float(df_1w.iloc[-2]["high"])
    except Exception:
        pass

    return levels


def _relevance_label(age_hours: float, max_age: float) -> str:
    ratio = age_hours / max_age if max_age > 0 else 1.0
    if ratio <= 0.25:
        return "HIGH"
    if ratio <= 0.50:
        return "MEDIUM"
    if ratio <= 0.75:
        return "LOW"
    return "STALE"


def _relevance_pts(age_hours: float, max_age: float) -> tuple[float, float]:
    ratio = age_hours / max_age if max_age > 0 else 1.0
    if ratio <= 0.25:
        return 12.0, 1.0
    if ratio <= 0.50:
        return 9.0,  0.67
    if ratio <= 0.75:
        return 6.0,  0.33
    if ratio <= 1.0:
        return 3.0,  0.15
    return 0.0, 0.0


def _detect_displacement(
    df:        pd.DataFrame,
    atr:       float,
    direction: str,
    after_idx: int,
    lookforward: int = 3,
) -> dict:
    if df is None or len(df) <= after_idx:
        return {"found": False, "score": 0.0}

    is_long  = direction == "LONG"
    vol_ma   = float(df["volume"].rolling(20).mean().iloc[-1]) or 1.0
    best     = {"found": False, "score": 0.0}
    end_idx  = min(after_idx + lookforward, len(df))

    for i in range(after_idx, end_idx):
        c     = df.iloc[i]
        body  = abs(float(c["close"]) - float(c["open"]))
        rng   = float(c["high"]) - float(c["low"])
        bull  = float(c["close"]) > float(c["open"])
        vs    = float(c["volume"]) / vol_ma

        if rng == 0:
            continue

        body_ratio = body / rng
        range_mult = rng / atr if atr > 0 else 0
        dir_match  = (is_long and bull) or (not is_long and not bull)

        if not dir_match or body_ratio < 0.60:
            continue

        score = round(
            min(body_ratio * 0.4 + min(range_mult / 3.0, 0.4) + (0.2 if vs >= 1.2 else 0.0), 1.0),
            3,
        )

        if score > best.get("score", 0.0):
            best = {
                "found":      True,
                "score":      score,
                "body_ratio": round(body_ratio, 3),
                "range_mult": round(range_mult, 3),
                "vol_spike":  round(vs, 2),
            }

    return best


def _check_below(
    df_1h:           pd.DataFrame,
    level:           Optional[float],
    label:           str,
    atr:             float,
    vol_ma:          float,
    lookback:        int,
    hours_per_candle:float,
    min_wick_atr:    float,
    price:           float,
) -> Optional[SweepLevel]:
    if not level or level <= 0:
        return None

    sl  = df_1h.tail(lookback)
    max_age = HE["sweep_max_age_hours"]

    for i in range(len(sl) - 1):
        c = sl.iloc[i]
        if not (float(c["low"]) < level and float(c["close"]) > level):
            continue

        wick = level - float(c["low"])
        if wick < atr * min_wick_atr:
            continue

        vs = float(c["volume"]) / vol_ma
        if vs < 1.2:
            continue

        candles_ago = len(sl) - 1 - i
        age_hours   = candles_ago * hours_per_candle
        rel_pts, rel_mult = _relevance_pts(age_hours, max_age)

        if rel_mult == 0:
            continue

        body_below = min(float(c["open"]), float(c["close"])) < level
        intensity  = min(10,
            (3 if wick / atr > 0.5 else 1) +
            (3 if vs > 1.5 else 1 if vs > 1.0 else 0) +
            2 +
            (2 if not body_below else 0)
        )

        if intensity < 6:
            continue

        confirmed  = bool(float(c["close"]) > level and price > level)
        raw_score  = rel_pts * (intensity / 10)
        adj_score  = raw_score if confirmed else round(raw_score * 0.65, 2)

        abs_idx    = len(df_1h) - len(sl) + i
        disp       = _detect_displacement(df_1h, atr, "LONG", abs_idx + 1)

        if disp["found"]:
            adj_score = round(adj_score * 1.3, 2)

        return SweepLevel(
            type         = "bull",
            label        = label,
            level        = float(level),
            sweep_low    = float(c["low"]),
            sweep_high   = None,
            wick         = round(wick, 6),
            wick_atr     = round(wick / atr, 2),
            vol_ratio    = round(vs, 2),
            intensity    = intensity,
            confirmed    = confirmed,
            candles_ago  = candles_ago,
            age_hours    = round(age_hours, 1),
            score        = adj_score,
            priority     = 1 if "weekly" in label.lower() else 2,
            displacement = disp,
        )

    return None


def _check_above(
    df_1h:           pd.DataFrame,
    level:           Optional[float],
    label:           str,
    atr:             float,
    vol_ma:          float,
    lookback:        int,
    hours_per_candle:float,
    min_wick_atr:    float,
    price:           float,
) -> Optional[SweepLevel]:
    if not level or level <= 0:
        return None

    sl      = df_1h.tail(lookback)
    max_age = HE["sweep_max_age_hours"]

    for i in range(len(sl) - 1):
        c = sl.iloc[i]
        if not (float(c["high"]) > level and float(c["close"]) < level):
            continue

        wick = float(c["high"]) - level
        if wick < atr * min_wick_atr:
            continue

        vs = float(c["volume"]) / vol_ma
        if vs < 1.2:
            continue

        candles_ago = len(sl) - 1 - i
        age_hours   = candles_ago * hours_per_candle
        rel_pts, rel_mult = _relevance_pts(age_hours, max_age)

        if rel_mult == 0:
            continue

        body_above = max(float(c["open"]), float(c["close"])) > level
        intensity  = min(10,
            (3 if wick / atr > 0.5 else 1) +
            (3 if vs > 1.5 else 1 if vs > 1.0 else 0) +
            2 +
            (2 if not body_above else 0)
        )

        if intensity < 6:
            continue

        confirmed  = bool(float(c["close"]) < level and price < level)
        raw_score  = rel_pts * (intensity / 10)
        adj_score  = raw_score if confirmed else round(raw_score * 0.65, 2)

        abs_idx    = len(df_1h) - len(sl) + i
        disp       = _detect_displacement(df_1h, atr, "SHORT", abs_idx + 1)

        if disp["found"]:
            adj_score = round(adj_score * 1.3, 2)

        return SweepLevel(
            type         = "bear",
            label        = label,
            level        = float(level),
            sweep_low    = None,
            sweep_high   = float(c["high"]),
            wick         = round(wick, 6),
            wick_atr     = round(wick / atr, 2),
            vol_ratio    = round(vs, 2),
            intensity    = intensity,
            confirmed    = confirmed,
            candles_ago  = candles_ago,
            age_hours    = round(age_hours, 1),
            score        = adj_score,
            priority     = 1 if "weekly" in label.lower() else 2,
            displacement = disp,
        )

    return None