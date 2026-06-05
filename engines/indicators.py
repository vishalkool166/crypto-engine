import pandas as pd
import ta
import numpy as np
from typing import Optional

def calculate_all(df: pd.DataFrame) -> dict:
    """
    Single function — calculates everything
    Uses 'ta' library instead of pandas_ta
    """
    close  = df["close"]
    high   = df["high"]
    low    = df["low"]
    vol    = df["volume"]
    price  = float(close.iloc[-1])

    # ── EMAs ──
    ema20  = ta.trend.ema_indicator(close, window=20)
    ema50  = ta.trend.ema_indicator(close, window=50)
    ema200 = ta.trend.ema_indicator(close, window=200)

    e20  = _last(ema20)
    e50  = _last(ema50)
    e200 = _last(ema200)

    # ── EMA Slopes ──
    slope20 = _slope(ema20, 5)
    slope50 = _slope(ema50, 5)

    # ── RSI ──
    rsi_series = ta.momentum.rsi(close, window=14)
    rsi        = _last(rsi_series)

    # ── MACD ──
    macd_obj  = ta.trend.MACD(close)
    macd      = _parse_macd(macd_obj)

    # ── ATR ──
    atr_series = ta.volatility.average_true_range(high, low, close, window=14)
    atr        = _last(atr_series)

    # ── ADX ──
    adx_series = ta.trend.adx(high, low, close, window=14)
    adx        = _last(adx_series)

    # ── Bollinger Bands ──
    bb     = _parse_bb(close, price)

    # ── Volume ──
    vol_ma5  = float(vol.rolling(5).mean().iloc[-1])
    vol_ma10 = float(vol.rolling(10).mean().iloc[-1])
    cur_vol  = float(vol.iloc[-2])

    # ── Trend ──
    trend = _get_trend(price, e20, e50, e200)

    # ── Swings ──
    swings = _find_swings(df, 50)

    # ── Structure ──
    structure = _detect_structure(df, swings, price)

    # ── FVG ──
    fvgs = _detect_fvg(df)

    # ── Volume Profile ──
    vp = _volume_profile(df, bins=50)

    # ── CVD ──
    cvd = _calculate_cvd(df)

    # ── Divergence ──
    divergence = _detect_divergence(df, rsi_series)

    # ── Last 5 candles ──
    last5 = _last5(df)

    return {
        "price":      price,
        "ema20":      e20,
        "ema50":      e50,
        "ema200":     e200,
        "slope20":    slope20,
        "slope50":    slope50,
        "rsi":        rsi,
        "macd":       macd,
        "atr":        atr,
        "adx":        adx,
        "bb":         bb,
        "vol_ma5":    vol_ma5,
        "vol_ma10":   vol_ma10,
        "cur_vol":    cur_vol,
        "trend":      trend,
        "swings":     swings,
        "structure":  structure,
        "fvgs":       fvgs,
        "poc":        vp["poc"],
        "vah":        vp["vah"],
        "val":        vp["val"],
        "cvd":        cvd,
        "divergence": divergence,
        "last5":      last5
    }

# ── PRIVATE HELPERS ──

def _last(series) -> Optional[float]:
    if series is None or len(series) == 0:
        return None
    val = series.iloc[-1]
    return float(val) if not pd.isna(val) else None

def _slope(series, lookback: int = 5) -> Optional[float]:
    if series is None or len(series) < lookback:
        return None
    a = series.iloc[-lookback]
    b = series.iloc[-1]
    if pd.isna(a) or pd.isna(b) or a == 0:
        return None
    return float((b - a) / a * 100)

def _parse_macd(macd_obj) -> Optional[dict]:
    if macd_obj is None:
        return None
    try:
        hist  = float(macd_obj.macd_diff().iloc[-1])
        prev  = float(macd_obj.macd_diff().iloc[-2])
        prev2 = float(macd_obj.macd_diff().iloc[-3])
        if pd.isna(hist) or pd.isna(prev):
            return None
        return {
            "hist":       hist,
            "prev":       prev,
            "bullish":    hist > 0,
            "bearish":    hist < 0,
            "expanding":  abs(hist) > abs(prev),
            "exhausting": abs(prev) > abs(prev2) and abs(hist) < abs(prev)
        }
    except:
        return None

def _parse_bb(close, price: float) -> Optional[dict]:
    try:
        bb_obj = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        upper  = float(bb_obj.bollinger_hband().iloc[-1])
        mid    = float(bb_obj.bollinger_mavg().iloc[-1])
        lower  = float(bb_obj.bollinger_lband().iloc[-1])
        if pd.isna(upper) or pd.isna(lower):
            return None
        width = ((upper - lower) / mid * 100) if mid > 0 else 0
        pct_b = ((price - lower) / (upper - lower) * 100) if (upper - lower) > 0 else 50
        return {
            "upper": upper,
            "mid":   mid,
            "lower": lower,
            "width": width,
            "pct_b": pct_b
        }
    except:
        return None

def _get_trend(price, e20, e50, e200) -> dict:
    score = 0
    if e200 and price > e200: score += 1
    if e50  and price > e50:  score += 1
    if e20  and price > e20:  score += 1
    if e20  and e50  and e20 > e50:  score += 1
    if e50  and e200 and e50 > e200: score += 1
    if score >= 4:
        return {"label": "Bullish", "cls": "bull", "score": score}
    if score <= 1:
        return {"label": "Bearish", "cls": "bear", "score": score}
    return {"label": "Neutral", "cls": "neutral", "score": score}

def _find_swings(df: pd.DataFrame, lookback: int = 50) -> dict:
    sl     = df.tail(lookback)
    highs  = []
    lows   = []
    n      = len(sl)

    for i in range(2, n - 2):
        h = sl["high"].iloc[i]
        if (h > sl["high"].iloc[i-1] and
            h > sl["high"].iloc[i-2] and
            h > sl["high"].iloc[i+1] and
            h > sl["high"].iloc[i+2]):
            highs.append({"price": h, "idx": i})

        l = sl["low"].iloc[i]
        if (l < sl["low"].iloc[i-1] and
            l < sl["low"].iloc[i-2] and
            l < sl["low"].iloc[i+1] and
            l < sl["low"].iloc[i+2]):
            lows.append({"price": l, "idx": i})

    return {
        "highs":     highs,
        "lows":      lows,
        "last_high": highs[-1] if highs else None,
        "last_low":  lows[-1]  if lows  else None,
        "prev_high": highs[-2] if len(highs) > 1 else None,
        "prev_low":  lows[-2]  if len(lows)  > 1 else None
    }

def _detect_structure(df, swings, price) -> dict:
    events = []
    lh = swings["last_high"]
    ll = swings["last_low"]
    ph = swings["prev_high"]
    pl = swings["prev_low"]

    if lh and price > lh["price"]:
        events.append({
            "type":  "BOS",
            "bias":  "bull",
            "label": "BOS Bullish",
            "desc":  f"Broke swing high {lh['price']:.2f}"
        })
    if ll and price < ll["price"]:
        events.append({
            "type":  "BOS",
            "bias":  "bear",
            "label": "BOS Bearish",
            "desc":  f"Broke swing low {ll['price']:.2f}"
        })
    if ph and lh and lh["price"] < ph["price"] and price > lh["price"]:
        events.append({
            "type":  "CHoCH",
            "bias":  "bull",
            "label": "CHoCH Bullish",
            "desc":  "Lower high broken — reversal up"
        })
    if pl and ll and ll["price"] > pl["price"] and price < ll["price"]:
        events.append({
            "type":  "CHoCH",
            "bias":  "bear",
            "label": "CHoCH Bearish",
            "desc":  "Higher low broken — reversal down"
        })

    bias = "neutral"
    if lh and ll and ph and pl:
        hh = lh["price"] > ph["price"]
        hl = ll["price"] > pl["price"]
        lh_ = lh["price"] < ph["price"]
        ll_ = ll["price"] < pl["price"]
        if hh and hl:    bias = "bull"
        elif lh_ and ll_: bias = "bear"

    return {"events": events, "struct_bias": bias}

def _detect_fvg(df: pd.DataFrame) -> list:
    fvgs = []
    sl   = df.tail(30)
    for i in range(2, len(sl)):
        c1 = sl.iloc[i-2]
        c3 = sl.iloc[i]
        if c1["high"] < c3["low"]:
            fvgs.append({
                "type":   "bull",
                "top":    float(c3["low"]),
                "bottom": float(c1["high"]),
                "mid":    float((c3["low"] + c1["high"]) / 2),
                "label":  "Bullish FVG"
            })
        if c1["low"] > c3["high"]:
            fvgs.append({
                "type":   "bear",
                "top":    float(c1["low"]),
                "bottom": float(c3["high"]),
                "mid":    float((c1["low"] + c3["high"]) / 2),
                "label":  "Bearish FVG"
            })
    return fvgs[-3:]

def _volume_profile(df: pd.DataFrame, bins: int = 50) -> dict:
    price_min = float(df["low"].min())
    price_max = float(df["high"].max())
    bin_size  = (price_max - price_min) / bins

    if bin_size == 0:
        p = float(df["close"].iloc[-1])
        return {"poc": p, "vah": p, "val": p}

    vol_at_price = np.zeros(bins)

    for _, c in df.iterrows():
        rng = c["high"] - c["low"]
        if rng == 0:
            continue
        for b in range(bins):
            b_low    = price_min + b * bin_size
            b_high   = b_low + bin_size
            overlap  = min(c["high"], b_high) - max(c["low"], b_low)
            if overlap > 0:
                vol_at_price[b] += c["volume"] * (overlap / rng)

    poc_idx = int(np.argmax(vol_at_price))
    total   = vol_at_price.sum()
    target  = total * 0.70
    vah_idx = poc_idx
    val_idx = poc_idx
    accum   = vol_at_price[poc_idx]

    while accum < target:
        up   = vol_at_price[vah_idx + 1] if vah_idx + 1 < bins else 0
        down = vol_at_price[val_idx - 1] if val_idx - 1 >= 0  else 0
        if up >= down and vah_idx + 1 < bins:
            vah_idx += 1
            accum   += up
        elif val_idx - 1 >= 0:
            val_idx -= 1
            accum   += down
        else:
            break

    return {
        "poc": price_min + (poc_idx + 0.5) * bin_size,
        "vah": price_min + (vah_idx + 0.5) * bin_size,
        "val": price_min + (val_idx + 0.5) * bin_size
    }

def _calculate_cvd(df: pd.DataFrame) -> dict:
    delta = []
    for _, c in df.iterrows():
        rng = c["high"] - c["low"]
        if rng == 0:
            delta.append(0)
            continue
        buy_ratio  = (c["close"] - c["low"])  / rng
        sell_ratio = (c["high"]  - c["close"]) / rng
        delta.append(c["volume"] * (buy_ratio - sell_ratio))

    cvd_series = pd.Series(delta).cumsum()
    price      = df["close"]
    price_up   = float(price.iloc[-1]) > float(price.iloc[-10])
    cvd_up     = float(cvd_series.iloc[-1]) > float(cvd_series.iloc[-10])

    div = "none"
    if price_up  and not cvd_up: div = "bearish"
    if not price_up and cvd_up:  div = "bullish"

    return {
        "value":      float(cvd_series.iloc[-1]),
        "divergence": div
    }

def _detect_divergence(df, rsi_series) -> dict:
    if rsi_series is None or len(rsi_series) < 20:
        return {"type": "none", "label": "None detected", "desc": ""}

    close = df["close"]
    lb    = 30
    ps    = close.tail(lb).values
    rs    = rsi_series.tail(lb).values

    ph, pl = [], []
    for i in range(2, lb - 2):
        if (ps[i] > ps[i-1] and ps[i] > ps[i-2] and
                ps[i] > ps[i+1] and ps[i] > ps[i+2]):
            ph.append({"v": ps[i], "ri": rs[i]})
        if (ps[i] < ps[i-1] and ps[i] < ps[i-2] and
                ps[i] < ps[i+1] and ps[i] < ps[i+2]):
            pl.append({"v": ps[i], "ri": rs[i]})

    if len(ph) >= 2:
        a, b = ph[-2], ph[-1]
        if b["v"] > a["v"] and b["ri"] < a["ri"]:
            return {
                "type":  "bearish",
                "label": "Bearish Divergence",
                "desc":  "Price HH, RSI LH"
            }
    if len(pl) >= 2:
        a, b = pl[-2], pl[-1]
        if b["v"] < a["v"] and b["ri"] > a["ri"]:
            return {
                "type":  "bullish",
                "label": "Bullish Divergence",
                "desc":  "Price LL, RSI HL"
            }
        if b["v"] > a["v"] and b["ri"] < a["ri"]:
            return {
                "type":  "hidden-bull",
                "label": "Hidden Bull Div",
                "desc":  "Price HL, RSI LL"
            }
    if len(ph) >= 2:
        a, b = ph[-2], ph[-1]
        if b["v"] < a["v"] and b["ri"] > a["ri"]:
            return {
                "type":  "hidden-bear",
                "label": "Hidden Bear Div",
                "desc":  "Price LH, RSI HH"
            }

    return {"type": "none", "label": "None detected", "desc": ""}

def _last5(df: pd.DataFrame) -> list:
    sl     = df.tail(5)
    result = []
    for _, c in sl.iterrows():
        pct = (c["close"] - c["open"]) / c["open"] * 100
        result.append({
            "open":  float(c["open"]),
            "high":  float(c["high"]),
            "low":   float(c["low"]),
            "close": float(c["close"]),
            "vol":   float(c["volume"]),
            "pct":   float(pct)
        })
    return result