"""Signal Engine 3.0: deterministic, research-only strategy candidates.

All inputs MUST be closed OHLCV candles. No strategy in this file can submit an
order or be promoted into production automatically. Configs are immutable per run.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Mapping

import pandas as pd

STRATEGIES = {
    "trend_continuation": "Trend continuation",
    "breakout_retest": "Breakout / continuation",
    "range_reversion": "Range mean reversion",
    "momentum_reversal": "Momentum reversal",
}
STRATEGY_RELEASE = "3.0.0-research.1"
MIN_BARS = 220


@dataclass(frozen=True)
class Candidate:
    strategy: str
    direction: str
    entry: float
    stop: float
    target: float
    score: float
    regime: str
    reason: str
    observed_at: str
    executable: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def features(frame: pd.DataFrame) -> pd.DataFrame:
    required = ("open", "high", "low", "close", "volume")
    if frame is None or not all(k in frame for k in required):
        raise ValueError("Complete OHLCV data required")
    d = frame.loc[:, list(required)].copy().astype(float)
    if len(d) < MIN_BARS or not d.index.is_unique or not d.index.is_monotonic_increasing:
        raise ValueError("Need >=220 sorted unique CLOSED candles")
    if not d.notna().all().all() or not all((d[k] > 0).all() for k in ("open", "high", "low", "close")) or not (d.volume >= 0).all():
        raise ValueError("Invalid OHLCV data")
    if not ((d.high >= d[["open", "close", "low"]].max(axis=1)) & (d.low <= d[["open", "close", "high"]].min(axis=1))).all():
        raise ValueError("Invalid candle price bounds")
    d["ema20"] = d.close.ewm(span=20, adjust=False).mean()
    d["ema50"] = d.close.ewm(span=50, adjust=False).mean()
    d["ema200"] = d.close.ewm(span=200, adjust=False).mean()
    tr = pd.concat([d.high - d.low, (d.high-d.close.shift()).abs(), (d.low-d.close.shift()).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1/14, adjust=False).mean()
    up = d.close.diff().clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    down = (-d.close.diff().clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = up / down.replace(0, float('nan'))
    d["rsi"] = (100 - 100/(1+rs)).fillna(50)
    basis = d.close.rolling(20).mean()
    sd = d.close.rolling(20).std(ddof=0)
    d["upper"] = basis + 2 * sd
    d["lower"] = basis - 2 * sd
    d["vol_ratio"] = d.volume / d.volume.shift(1).rolling(20).mean().replace(0, float('nan'))
    d["prior_high"] = d.high.shift(1).rolling(20).max()
    d["prior_low"] = d.low.shift(1).rolling(20).min()
    # ADX using Wilder smoothing; meaningful only after warmup.
    plus_dm = d.high.diff().where((d.high.diff() > (-d.low.diff())) & (d.high.diff() > 0), 0.0)
    minus_dm = (-d.low.diff()).where(((-d.low.diff()) > d.high.diff()) & ((-d.low.diff()) > 0), 0.0)
    trs = tr.ewm(alpha=1/14, adjust=False).mean().replace(0, float('nan'))
    pdi = 100 * plus_dm.ewm(alpha=1/14, adjust=False).mean() / trs
    mdi = 100 * minus_dm.ewm(alpha=1/14, adjust=False).mean() / trs
    dx = 100 * (pdi-mdi).abs() / (pdi+mdi).replace(0, float('nan'))
    d["adx"] = dx.ewm(alpha=1/14, adjust=False).mean().fillna(0)
    return d


def regime(d: pd.DataFrame) -> str:
    p = d.iloc[-1]
    atr_percent = p.atr / p.close
    if not math.isfinite(atr_percent) or atr_percent >= .085:
        return "unstable"
    if p.adx >= 24:
        return "trending"
    if p.adx < 19:
        return "ranging"
    return "transition"


def evaluate(d: pd.DataFrame, strategy: str, params: Mapping | None = None) -> dict:
    """Evaluate one closed-candle feature frame; emit candidate OR explicit rejection."""
    if strategy not in STRATEGIES:
        raise ValueError("Unregistered strategy")
    if len(d) < MIN_BARS:
        raise ValueError("Insufficient data")
    params = params or {}
    volume_floor = float(params.get("min_volume_ratio", 1.2))
    if not .5 <= volume_floor <= 4 or not math.isfinite(volume_floor):
        raise ValueError("min_volume_ratio must be in [0.5,4]")
    x, prev = d.iloc[-1], d.iloc[-2]
    status = regime(d)
    ts = str(d.index[-1])
    rejected = lambda why: {"strategy": strategy, "candidate": None, "rejection": why, "regime": status, "observed_at": ts}
    if not all(math.isfinite(float(x[k])) for k in ("close","atr","rsi","adx","vol_ratio","ema20","ema50","ema200","prior_high","prior_low")):
        return rejected("invalid_features")
    if status == "unstable" or x.atr <= 0:
        return rejected("unstable_or_invalid_atr")
    direction, why = None, "conditions_not_met"
    if strategy == "trend_continuation":
        direction = "LONG" if x.ema20 > x.ema50 > x.ema200 and x.close > x.ema20 else "SHORT" if x.ema20 < x.ema50 < x.ema200 and x.close < x.ema20 else None
        if status != "trending" or x.vol_ratio < volume_floor or direction is None or abs(x.close - x.ema20) > 1.3*x.atr:
            return rejected("no_trend_pullback_confirmation")
    elif strategy == "breakout_retest":
        # A completed breakout candle FOLLOWED by a separate retest candle.
        # The breakout boundary excludes both the breakout and retest bars.
        upper_at_breakout = float(d.high.iloc[-22:-2].max())
        lower_at_breakout = float(d.low.iloc[-22:-2].min())
        breakout_up = prev.close > upper_at_breakout and prev.vol_ratio >= volume_floor
        breakout_down = prev.close < lower_at_breakout and prev.vol_ratio >= volume_floor
        direction = (
            "LONG" if breakout_up and x.low <= upper_at_breakout * 1.003 and x.close > upper_at_breakout and x.close > x.open
            else "SHORT" if breakout_down and x.high >= lower_at_breakout * .997 and x.close < lower_at_breakout and x.close < x.open
            else None
        )
        if direction is None:
            return rejected("breakout_without_confirmed_retest")
    elif strategy == "range_reversion":
        direction = "LONG" if x.low < x.lower and x.close > x.lower and x.rsi < 40 else "SHORT" if x.high > x.upper and x.close < x.upper and x.rsi > 60 else None
        if status != "ranging" or direction is None or x.vol_ratio < .5:
            return rejected("no_range_rejection")
    else:
        # Sweep and reclaim 20-bar liquidity, with momentum rollover evidence.
        direction = "LONG" if x.low < x.prior_low and x.close > x.prior_low and x.close > x.open and x.rsi < 48 else "SHORT" if x.high > x.prior_high and x.close < x.prior_high and x.close < x.open and x.rsi > 52 else None
        if direction is None or x.vol_ratio < volume_floor or status == "trending" and x.adx > 38:
            return rejected("no_reversal_structure")
    entry = float(x.close)
    stop = float(min(x.low - .3*x.atr, entry - 1.3*x.atr) if direction == "LONG" else max(x.high + .3*x.atr, entry + 1.3*x.atr))
    distance = abs(entry-stop)
    if not 0.003 <= distance/entry <= .07:
        return rejected("risk_distance_out_of_bounds")
    rr = 1.8 if strategy in ("range_reversion","momentum_reversal") else 2.0
    target = entry + distance * rr * (1 if direction == "LONG" else -1)
    if stop <= 0 or target <= 0:
        return rejected("invalid_protective_levels")
    score = min(95., round(48 + min(18., x.adx/2) + min(18.,x.vol_ratio*7) + (8 if status=="trending" else 0),1))
    return {"strategy":strategy, "candidate":Candidate(strategy, direction, entry, stop, target, score, status, why, ts).to_dict(), "rejection":None, "regime":status,"observed_at":ts}


def scan(frame: pd.DataFrame, params: Mapping | None = None, only: str | None = None) -> list[dict]:
    d = features(frame)
    return [evaluate(d, name, params) for name in (STRATEGIES if only is None else (only,))]
