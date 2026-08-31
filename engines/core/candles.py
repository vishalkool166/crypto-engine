import pandas as pd


def is_bullish(candle: pd.Series) -> bool:
    return float(candle["close"]) > float(candle["open"])


def is_bearish(candle: pd.Series) -> bool:
    return float(candle["close"]) < float(candle["open"])


def body_ratio(candle: pd.Series) -> float:
    o   = float(candle["open"])
    c   = float(candle["close"])
    h   = float(candle["high"])
    l   = float(candle["low"])
    rng = h - l
    if rng == 0:
        return 0.0
    return round(abs(c - o) / rng, 3)


def is_momentum_candle(candle: pd.Series, min_body_ratio: float = 0.6) -> bool:
    return body_ratio(candle) >= min_body_ratio


def touches_level(candle: pd.Series, level: float, buffer: float) -> bool:
    return float(candle["low"]) <= level + buffer and float(candle["high"]) >= level - buffer


def is_near_level(price: float, level: float, atr: float, mult: float = 0.5) -> bool:
    return abs(price - level) <= atr * mult