"""Signal Engine: deterministic strategy candidates shared by live and replay.

All inputs MUST be closed OHLCV candles. Strategy modules emit proposals only.
The unified pipeline applies central risk sizing; only the existing exchange
executor can submit an order. Configs are immutable per scan.
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
STRATEGY_RELEASE = "3.4.0-structure-aware"
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


def _structure_levels(d: pd.DataFrame, strategy: str, direction: str, *,
                      boundary: float | None = None) -> tuple[float, float, str]:
    """Stop invalidation and observable target zone from *past closed* candles.

    Does not guess that a reward multiple is reachable. No liquidity or order-book
    claim is made from OHLCV: this is a conservative candle-structure proxy.
    """
    x = d.iloc[-1]
    entry, atr = float(x.close), float(x.atr)
    recent = d.iloc[-21:-1]
    context = d.iloc[-121:-1]
    if direction == "LONG":
        invalidation = (
            float(recent.low.min()) if strategy == 'trend_continuation' else
            min(float(x.low), float(boundary)) if strategy == 'breakout_retest' and boundary is not None else
            min(float(recent.low.min()), float(x.low)) if strategy == 'range_reversion' else
            float(x.low)
        )
        stop = invalidation - .25 * atr
        # Previous swing highs are the first nearby area of opposing structure.
        swing = context.high[(context.high > entry * (1 + 0.0001))]
        if swing.empty and strategy == 'breakout_retest' and boundary is not None:
            # A breakout into uncharted territory uses the measured prior
            # closed-candle range; not an arbitrary risk/reward multiple.
            target = float(boundary) + (float(recent.high.max()) - float(recent.low.min()))
            source = 'measured_prior_range'
        elif swing.empty:
            return stop, float('nan'), 'no_observable_resistance'
        else:
            target = float(swing.min()) - .10 * atr
            source = 'nearest_observed_resistance'
    else:
        invalidation = (
            float(recent.high.max()) if strategy == 'trend_continuation' else
            max(float(x.high), float(boundary)) if strategy == 'breakout_retest' and boundary is not None else
            max(float(recent.high.max()), float(x.high)) if strategy == 'range_reversion' else
            float(x.high)
        )
        stop = invalidation + .25 * atr
        swing = context.low[(context.low < entry * (1 - 0.0001))]
        if swing.empty and strategy == 'breakout_retest' and boundary is not None:
            target = float(boundary) - (float(recent.high.max()) - float(recent.low.min()))
            source = 'measured_prior_range'
        elif swing.empty:
            return stop, float('nan'), 'no_observable_support'
        else:
            target = float(swing.max()) + .10 * atr
            source = 'nearest_observed_support'
    if strategy == 'range_reversion':
        # A range setup exits at the historical range midpoint first, rather
        # than at an arbitrary extension beyond the other boundary.
        midpoint = (float(recent.high.max()) + float(recent.low.min())) / 2
        target = min(target, midpoint) if direction == 'LONG' else max(target, midpoint)
        source = 'range_midpoint_and_structure'
    return stop, target, source


def evaluate(d: pd.DataFrame, strategy: str, params: Mapping | None = None) -> dict:
    """Same closed-candle evaluation for scanner and replay, with evidence."""
    if strategy not in STRATEGIES:
        raise ValueError('Unregistered strategy')
    if len(d) < MIN_BARS:
        raise ValueError('Insufficient data')
    params = params or {}
    volume_floor = float(params.get('min_volume_ratio', 1.2))
    if not .5 <= volume_floor <= 4 or not math.isfinite(volume_floor):
        raise ValueError('min_volume_ratio must be in [0.5,4]')
    x, prev = d.iloc[-1], d.iloc[-2]
    status, ts = regime(d), str(d.index[-1])
    checks: list[dict] = []
    def check(name: str, actual, expected: str, passed: bool):
        actual = float(actual) if isinstance(actual, (float, int)) and math.isfinite(float(actual)) else str(actual)
        checks.append({'name':name, 'actual':actual,'required':expected,'passed':bool(passed)})
        return bool(passed)
    def rejected(why: str):
        return {'strategy':strategy,'candidate':None,'rejection':why,'regime':status,
                'observed_at':ts,'checks':checks}
    required = ('close','atr','rsi','adx','vol_ratio','ema20','ema50','ema200','prior_high','prior_low')
    valid = all(math.isfinite(float(x[k])) for k in required)
    check('Indicator data', 'complete' if valid else 'missing/non-finite','all required values finite',valid)
    if not valid:
        return rejected('invalid_features')
    stable = status != 'unstable' and float(x.atr) > 0
    check('Volatility regime',status,'not unstable; ATR positive',stable)
    if not stable:
        return rejected('unstable_or_invalid_atr')
    direction, why, boundary = None, 'conditions_not_met', None
    if strategy == 'trend_continuation':
        long_align = x.ema20 > x.ema50 > x.ema200 and x.close > x.ema20
        short_align = x.ema20 < x.ema50 < x.ema200 and x.close < x.ema20
        direction = 'LONG' if long_align else 'SHORT' if short_align else None
        a=check('Market regime',status,'trending / ADX >= 24',status=='trending')
        b=check('EMA alignment', 'bullish' if long_align else 'bearish' if short_align else 'mixed','EMA20/50/200 ordered with price',direction is not None)
        c=check('Relative volume',x.vol_ratio,f'>= {volume_floor:.2f}x',x.vol_ratio>=volume_floor)
        distance = abs(float(x.close-x.ema20))/float(x.atr)
        e=check('Pullback proximity',distance,'<= 1.30 ATR from EMA20',distance<=1.3)
        check('ADX strength',x.adx,'>= 24',x.adx>=24)
        if not all((a,b,c,e)):
            return rejected('no_trend_pullback_confirmation')
        why = 'trend_pullback_confirmed'
    elif strategy == 'breakout_retest':
        upper=float(d.high.iloc[-22:-2].max()); lower=float(d.low.iloc[-22:-2].min())
        up=prev.close>upper and prev.vol_ratio>=volume_floor
        down=prev.close<lower and prev.vol_ratio>=volume_floor
        check('Breakout candle',f'prev close {prev.close:.8g}, range {lower:.8g}–{upper:.8g}',f'outside previous 20-bar range with >= {volume_floor}x volume',up or down)
        long_retest=up and x.low<=upper*1.003 and x.close>upper and x.close>x.open
        short_retest=down and x.high>=lower*.997 and x.close<lower and x.close<x.open
        direction='LONG' if long_retest else 'SHORT' if short_retest else None
        check('Retest confirmation', 'bullish' if long_retest else 'bearish' if short_retest else 'absent','separate reclaim candle',direction is not None)
        if direction is None:
            return rejected('breakout_without_confirmed_retest')
        boundary=upper if direction=='LONG' else lower
        why='breakout_retest_confirmed'
    elif strategy == 'range_reversion':
        long_reject=x.low<x.lower and x.close>x.lower and x.rsi<40
        short_reject=x.high>x.upper and x.close<x.upper and x.rsi>60
        direction='LONG' if long_reject else 'SHORT' if short_reject else None
        a=check('Market regime',status,'ranging / ADX < 19',status=='ranging')
        b=check('Band rejection', 'low/high beyond band, recovered' if direction else 'no confirmed rejection','Bollinger boundary reclaimed with RSI extreme',direction is not None)
        c=check('Relative volume',x.vol_ratio,'>= 0.50x',x.vol_ratio>=.5)
        check('RSI',x.rsi,'< 40 long / > 60 short',x.rsi<40 or x.rsi>60)
        if not all((a,b,c)):
            return rejected('no_range_rejection')
        why='range_rejection_confirmed'
    else:
        up=x.low<x.prior_low and x.close>x.prior_low and x.close>x.open and x.rsi<48
        down=x.high>x.prior_high and x.close<x.prior_high and x.close<x.open and x.rsi>52
        direction='LONG' if up else 'SHORT' if down else None
        a=check('Liquidity sweep and reclaim','bullish' if up else 'bearish' if down else 'absent','close back within prior 20-bar level + RSI',direction is not None)
        b=check('Relative volume',x.vol_ratio,f'>= {volume_floor:.2f}x',x.vol_ratio>=volume_floor)
        c=check('Trend exhaustion',x.adx,'ADX <= 38 when trending',not(status=='trending' and x.adx>38))
        check('RSI',x.rsi,'< 48 bullish / > 52 bearish',x.rsi<48 or x.rsi>52)
        if not all((a,b,c)):
            return rejected('no_reversal_structure')
        why='liquidity_reversal_confirmed'
    entry=float(x.close)
    stop,target,target_source=_structure_levels(d,strategy,direction,boundary=boundary)
    valid_levels=all(math.isfinite(v) and v>0 for v in (entry,stop,target))
    check('Structure-defined levels',target_source,'valid candle-observed support/resistance or range projection',valid_levels)
    if not valid_levels:
        return rejected('no_viable_structural_target')
    risk=abs(entry-stop)
    valid_risk=0.003 <= risk/entry <= .07
    check('Stop distance',100*risk/entry,'between 0.3% and 7% of entry',valid_risk)
    if not valid_risk:
        return rejected('risk_distance_out_of_bounds')
    directional=stop<entry<target if direction=='LONG' else target<entry<stop
    check('Target direction',round(target,8),'target beyond entry and stop beyond invalidation',directional)
    if not directional:
        return rejected('opposing_structure_blocks_target')
    rr=abs(target-entry)/risk
    minimum_rr=float(params.get('minimum_rr',1.8))
    check('Available reward / risk',rr,f'>= {minimum_rr:.2f}R before opposing structure',rr>=minimum_rr)
    if rr<minimum_rr:
        return rejected('insufficient_reward_before_structure')
    score=min(95.,round(48+min(18.,x.adx/2)+min(18.,x.vol_ratio*7)+(8 if status=='trending' else 0),1))
    candidate=Candidate(strategy,direction,entry,stop,target,score,status,why,ts).to_dict()
    candidate.update({'target_source':target_source,'available_rr':round(rr,3),
                      'stop_basis':'strategy_structure_invalidation_plus_0.25_ATR_buffer'})
    return {'strategy':strategy,'candidate':candidate,'rejection':None,
            'regime':status,'observed_at':ts,'checks':checks}

def scan(frame: pd.DataFrame, params: Mapping | None = None, only: str | None = None) -> list[dict]:
    d = features(frame)
    return [evaluate(d, name, params) for name in (STRATEGIES if only is None else (only,))]
