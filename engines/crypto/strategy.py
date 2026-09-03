import logging
import pandas as pd
from dataclasses import dataclass
from typing import Optional
from engines.core.indicators import get_indicators
from engines.core.candles import is_bullish, is_bearish, is_momentum_candle, is_near_level
from engines.core.regime import detect_regime
from engines.core.risk import calculate_risk, RiskResult

log = logging.getLogger(__name__)


@dataclass
class SignalResult:
    signal:     bool
    coin:       str
    direction:  str
    grade:      str
    score:      float
    entry:      float
    sl:         float
    tp1:        float
    tp2:        float
    sl_pct:     float
    sl_dist:    float
    rr1:        float
    rr2:        float
    risk_amt:   float
    pos_size:   float
    stake:      float
    leverage:   int
    risk_pct:   float
    adx:        float
    rsi:        float
    vol_ratio:  float
    regime:     str
    reason:     str


def analyze(
    coin:    str,
    df_4h:   pd.DataFrame,
    df_1h:   pd.DataFrame,
    balance: float,
) -> SignalResult:
    try:
        d4h = get_indicators(df_4h, timeframe="4h")
        d1h = get_indicators(df_1h, timeframe="1h")

        regime = detect_regime(d4h)

        if regime.is_volatile:
            return _no_signal(coin, "volatile_regime")

        price     = d4h["price"]
        ema50     = d4h["ema50"]
        ema200    = d4h["ema200"]
        adx       = d4h["adx"]
        atr       = d4h["atr"]
        vol_ratio = d4h["vol_ratio"]
        rsi       = d1h["rsi"]

        if not price or not ema200 or not ema50:
            return _no_signal(coin, "missing_indicators")

        if adx < 18:
            return _no_signal(coin, "adx_too_low")

        if price > ema200:
            direction = "LONG"
        elif price < ema200:
            direction = "SHORT"
        else:
            return _no_signal(coin, "ema_neutral")

        near_ema50 = abs(price - ema50) <= atr * 3.0
        if not near_ema50:
            return _no_signal(coin, "not_near_ema50")

        last_candle = df_4h.iloc[-1]
        if direction == "LONG" and not is_bullish(last_candle):
            return _no_signal(coin, "no_bullish_candle")
        if direction == "SHORT" and not is_bearish(last_candle):
            return _no_signal(coin, "no_bearish_candle")

        if not is_momentum_candle(last_candle, min_body_ratio=0.5):
            return _no_signal(coin, "weak_candle")

        if vol_ratio < 0.5:
            return _no_signal(coin, "low_volume")

        swing_level = d4h["swing_low"] if direction == "LONG" else d4h["swing_high"]

        risk = calculate_risk(
            direction   = direction,
            entry       = price,
            swing_level = swing_level,
            atr         = atr,
        )

        if not risk.valid:
            return _no_signal(coin, risk.reason)

        score = _calculate_score(adx, rsi, vol_ratio, direction)
        grade = _assign_grade(score)

        if grade == "F":
            return _no_signal(coin, "grade_f")

        from engines.sizing.adaptive import calculate as size_calc
        sizing = size_calc(
            balance     = balance,
            sl_pct      = risk.sl_pct,
            sl_dist     = risk.sl_dist,
            grade       = grade,
            direction   = direction,
            regime_mult = regime.size_mult,
        )

        if sizing.skip:
            return _no_signal(coin, sizing.reason)

        return SignalResult(
            signal    = True,
            coin      = coin,
            direction = direction,
            grade     = grade,
            score     = score,
            entry     = risk.entry,
            sl        = risk.sl,
            tp1       = risk.tp1,
            tp2       = risk.tp2,
            sl_pct    = risk.sl_pct,
            sl_dist   = risk.sl_dist,
            rr1       = risk.rr1,
            rr2       = risk.rr2,
            risk_amt  = sizing.risk_amt,
            pos_size  = sizing.position_size,
            stake     = sizing.stake,
            leverage  = sizing.leverage,
            risk_pct  = sizing.risk_pct,
            adx       = adx,
            rsi       = rsi,
            vol_ratio = vol_ratio,
            regime    = regime.label,
            reason    = "",
        )

    except Exception as e:
        log.error("strategy.analyze %s: %s", coin, e)
        return _no_signal(coin, str(e))


def _calculate_score(
    adx:       float,
    rsi:       float,
    vol_ratio: float,
    direction: str,
) -> float:
    score = 0.0

    if adx >= 30:
        score += 40
    elif adx >= 25:
        score += 30
    elif adx >= 18:
        score += 20

    if direction == "LONG":
        if rsi <= 40:
            score += 30
        elif rsi <= 50:
            score += 20
        elif rsi <= 55:
            score += 10
    else:
        if rsi >= 60:
            score += 30
        elif rsi >= 50:
            score += 20
        elif rsi >= 45:
            score += 10

    if vol_ratio >= 2.0:
        score += 30
    elif vol_ratio >= 1.5:
        score += 20
    elif vol_ratio >= 0.8:
        score += 10

    return round(score, 1)


def _assign_grade(score: float) -> str:
    if score >= 80:
        return "A+"
    if score >= 65:
        return "A"
    if score >= 50:
        return "B"
    return "F"


def _no_signal(coin: str, reason: str) -> SignalResult:
    return SignalResult(
        signal    = False,
        coin      = coin,
        direction = "NEUTRAL",
        grade     = "F",
        score     = 0.0,
        entry     = 0.0,
        sl        = 0.0,
        tp1       = 0.0,
        tp2       = 0.0,
        sl_pct    = 0.0,
        sl_dist   = 0.0,
        rr1       = 0.0,
        rr2       = 0.0,
        risk_amt  = 0.0,
        pos_size  = 0.0,
        stake     = 0.0,
        leverage  = 0,
        risk_pct  = 0.0,
        adx       = 0.0,
        rsi       = 0.0,
        vol_ratio = 0.0,
        regime    = "",
        reason    = reason,
    )