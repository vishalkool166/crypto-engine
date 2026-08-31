import pandas as pd
import ta
import numpy as np


def get_indicators(df: pd.DataFrame, timeframe: str = "4h") -> dict:
    close  = df["close"]
    high   = df["high"]
    low    = df["low"]
    vol    = df["volume"]
    price  = float(close.iloc[-1])

    ema20  = ta.trend.ema_indicator(close, window=20)
    ema50  = ta.trend.ema_indicator(close, window=50)
    ema200 = ta.trend.ema_indicator(close, window=200)

    e20  = _last(ema20)
    e50  = _last(ema50)
    e200 = _last(ema200)

    rsi = _last(ta.momentum.rsi(close, window=14))
    adx = _last(ta.trend.adx(high, low, close, window=14))
    atr = _last(ta.volatility.average_true_range(high, low, close, window=14))

    vol_ma20 = float(vol.rolling(20).mean().iloc[-1])
    cur_vol  = float(vol.iloc[-1])
    vol_ratio= round(cur_vol / vol_ma20, 3) if vol_ma20 > 0 else 1.0

    swing_high = _swing_high(df)
    swing_low  = _swing_low(df)

    return {
        "price":       price,
        "ema20":       e20,
        "ema50":       e50,
        "ema200":      e200,
        "rsi":         rsi,
        "adx":         adx,
        "atr":         atr,
        "vol_ma20":    vol_ma20,
        "cur_vol":     cur_vol,
        "vol_ratio":   vol_ratio,
        "swing_high":  swing_high,
        "swing_low":   swing_low,
    }


def _last(series) -> float:
    if series is None or len(series) == 0:
        return 0.0
    val = series.iloc[-1]
    return float(val) if not pd.isna(val) else 0.0


def _swing_high(df: pd.DataFrame, lookback: int = 50) -> float:
    sl = df.tail(lookback)
    n  = len(sl)
    for i in range(n - 2, 1, -1):
        h = float(sl["high"].iloc[i])
        if h > float(sl["high"].iloc[i - 1]) and h > float(sl["high"].iloc[i + 1]):
            return h
    return float(df["high"].max())


def _swing_low(df: pd.DataFrame, lookback: int = 50) -> float:
    sl = df.tail(lookback)
    n  = len(sl)
    for i in range(n - 2, 1, -1):
        l = float(sl["low"].iloc[i])
        if l < float(sl["low"].iloc[i - 1]) and l < float(sl["low"].iloc[i + 1]):
            return l
    return float(df["low"].min())