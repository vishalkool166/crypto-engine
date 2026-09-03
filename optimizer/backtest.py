import pandas as pd
import numpy as np
import logging
import ta

log = logging.getLogger(__name__)


def get_indicators(df: pd.DataFrame) -> dict:
    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    vol   = df["volume"]

    def _last(series):
        if series is None or len(series) == 0:
            return 0.0
        val = series.iloc[-1]
        return float(val) if not pd.isna(val) else 0.0

    ema20  = ta.trend.ema_indicator(close, window=20)
    ema50  = ta.trend.ema_indicator(close, window=50)
    ema200 = ta.trend.ema_indicator(close, window=200)
    rsi    = ta.momentum.rsi(close, window=14)
    adx    = ta.trend.adx(high, low, close, window=14)
    atr    = ta.volatility.average_true_range(high, low, close, window=14)

    vol_ma20  = float(vol.rolling(20).mean().iloc[-1]) if len(vol) >= 20 else 1.0
    cur_vol   = float(vol.iloc[-1])
    vol_ratio = round(cur_vol / vol_ma20, 3) if vol_ma20 > 0 else 1.0

    price = float(close.iloc[-1])
    atr_v = _last(atr)

    def _swing_high(lookback=50):
        sl = df.tail(lookback)
        n  = len(sl)
        for i in range(n - 2, 1, -1):
            h = float(sl["high"].iloc[i])
            if h > float(sl["high"].iloc[i-1]) and h > float(sl["high"].iloc[i+1]):
                return h
        return float(df["high"].max())

    def _swing_low(lookback=50):
        sl = df.tail(lookback)
        n  = len(sl)
        for i in range(n - 2, 1, -1):
            l = float(sl["low"].iloc[i])
            if l < float(sl["low"].iloc[i-1]) and l < float(sl["low"].iloc[i+1]):
                return l
        return float(df["low"].min())

    return {
        "price":       price,
        "ema20":       _last(ema20),
        "ema50":       _last(ema50),
        "ema200":      _last(ema200),
        "rsi":         _last(rsi),
        "adx":         _last(adx),
        "atr":         atr_v,
        "atr_pct":     round(atr_v / price * 100, 4) if price > 0 else 0.0,
        "vol_ratio":   vol_ratio,
        "swing_high":  _swing_high(),
        "swing_low":   _swing_low(),
    }


def check_signal(d4h: dict, d1h: dict, config: dict) -> dict:
    price  = d4h["price"]
    ema20  = d4h["ema20"]
    ema50  = d4h["ema50"]
    ema200 = d4h["ema200"]
    adx    = d4h["adx"]
    atr    = d4h["atr"]
    atr_pct= d4h["atr_pct"]
    vol    = d4h["vol_ratio"]
    rsi    = d1h["rsi"] if d1h else d4h["rsi"]

    adx_min     = config["adx_min"]
    rsi_max_long= config["rsi_max_long"]
    atr_pct_max = config["atr_pct_max"]
    vol_min     = config["vol_min"]

    if atr_pct > atr_pct_max:
        return {"signal": False, "reason": "volatile"}

    if adx < adx_min:
        return {"signal": False, "reason": "adx_too_low"}

    if not price or not ema200:
        return {"signal": False, "reason": "missing_indicators"}

    if price > ema200:
        direction = "LONG"
    elif price < ema200:
        direction = "SHORT"
    else:
        return {"signal": False, "reason": "ema_neutral"}

    buffer = atr * 0.05
    if direction == "LONG":
        strict  = price > ema20 + buffer and ema20 > ema50
        relaxed = price > ema20 + buffer * 2
        if not strict and not relaxed:
            return {"signal": False, "reason": "ema_neutral"}
    else:
        strict  = price < ema20 - buffer and ema20 < ema50
        relaxed = price < ema20 - buffer * 2
        if not strict and not relaxed:
            return {"signal": False, "reason": "ema_neutral"}

    if vol < vol_min:
        return {"signal": False, "reason": "low_volume"}

    if direction == "LONG" and rsi > rsi_max_long:
        return {"signal": False, "reason": "rsi_too_high"}
    if direction == "SHORT" and rsi < (100 - rsi_max_long):
        return {"signal": False, "reason": "rsi_too_low"}

    swing_level = d4h["swing_low"] if direction == "LONG" else d4h["swing_high"]
    sl_buffer   = atr * 0.5

    if direction == "LONG":
        sl = swing_level - sl_buffer
        if sl >= price:
            return {"signal": False, "reason": "sl_invalid"}
    else:
        sl = swing_level + sl_buffer
        if sl <= price:
            return {"signal": False, "reason": "sl_invalid"}

    sl_dist = abs(price - sl)
    sl_pct  = sl_dist / price * 100

    if sl_pct < 0.3:
        return {"signal": False, "reason": "sl_too_tight"}
    if sl_pct > 5.0:
        return {"signal": False, "reason": "sl_too_wide"}

    tp1 = price + sl_dist * 2.5 if direction == "LONG" else price - sl_dist * 2.5
    tp2 = price + sl_dist * 4.0 if direction == "LONG" else price - sl_dist * 4.0

    return {
        "signal":    True,
        "direction": direction,
        "entry":     price,
        "sl":        round(sl,  6),
        "tp1":       round(tp1, 6),
        "tp2":       round(tp2, 6),
        "sl_pct":    round(sl_pct, 3),
        "rr1":       2.5,
        "adx":       adx,
        "rsi":       rsi,
        "vol":       vol,
        "atr_pct":   atr_pct,
        "reason":    "",
    }


def simulate_trade(
    df_4h:     pd.DataFrame,
    bar_index: int,
    direction: str,
    entry:     float,
    sl:        float,
    tp1:       float,
    tp2:       float,
) -> dict:
    future  = df_4h.iloc[bar_index:bar_index + 60]
    is_long = direction == "LONG"
    tp1_hit = False

    if len(future) < 2:
        return {
            "outcome":    "timeout",
            "exit_price": entry,
            "candles":    0,
            "tp1_hit":    False,
            "pnl_r":      0.0,
        }

    sl_dist = abs(entry - sl)

    for j, (_, c) in enumerate(future.iterrows()):
        h = float(c["high"])
        l = float(c["low"])

        sl_hit  = (l <= sl)  if is_long else (h >= sl)
        tp1_now = (h >= tp1) if is_long else (l <= tp1)
        tp2_now = (h >= tp2) if is_long else (l <= tp2)

        if not tp1_hit:
            if sl_hit and tp1_now:
                return {
                    "outcome":    "loss",
                    "exit_price": sl,
                    "candles":    j + 1,
                    "tp1_hit":    False,
                    "pnl_r":      -1.0,
                }
            if sl_hit:
                return {
                    "outcome":    "loss",
                    "exit_price": sl,
                    "candles":    j + 1,
                    "tp1_hit":    False,
                    "pnl_r":      -1.0,
                }
            if tp1_now:
                tp1_hit = True
                sl      = entry
                if not tp2:
                    return {
                        "outcome":    "win",
                        "exit_price": tp1,
                        "candles":    j + 1,
                        "tp1_hit":    True,
                        "pnl_r":      2.5,
                    }
                continue
        else:
            if tp2_now:
                return {
                    "outcome":    "win",
                    "exit_price": tp2,
                    "candles":    j + 1,
                    "tp1_hit":    True,
                    "pnl_r":      4.0,
                }
            sl_hit_be = (l <= sl) if is_long else (h >= sl)
            if sl_hit_be:
                return {
                    "outcome":    "win",
                    "exit_price": entry,
                    "candles":    j + 1,
                    "tp1_hit":    True,
                    "pnl_r":      0.0,
                }

    last_close = float(future.iloc[-1]["close"])
    if tp1_hit:
        pnl_r = round((last_close - entry) / sl_dist, 2) if is_long else round((entry - last_close) / sl_dist, 2)
        return {
            "outcome":    "win",
            "exit_price": last_close,
            "candles":    len(future),
            "tp1_hit":    True,
            "pnl_r":      max(0.0, pnl_r),
        }

    return {
        "outcome":    "timeout",
        "exit_price": last_close,
        "candles":    len(future),
        "tp1_hit":    False,
        "pnl_r":      0.0,
    }


def run_backtest(
    df_4h:  pd.DataFrame,
    df_1h:  pd.DataFrame,
    config: dict,
    coin:   str = "",
) -> dict:

    if df_4h is None or len(df_4h) < 250:
        return {"error": f"Insufficient 4h data: {len(df_4h) if df_4h is not None else 0}"}

    trades      = []
    rejections  = {}
    min_bars    = 220

    for i in range(min_bars, len(df_4h) - 60):
        window_4h = df_4h.iloc[i - min_bars:i]

        ts_4h = df_4h.index[i]
        if df_1h is not None:
            window_1h = df_1h[df_1h.index <= ts_4h].tail(300)
            if len(window_1h) < 50:
                window_1h = None
        else:
            window_1h = None

        try:
            d4h = get_indicators(window_4h)
            d1h = get_indicators(window_1h) if window_1h is not None and len(window_1h) >= 50 else None
        except Exception:
            continue

        result = check_signal(d4h, d1h, config)

        if not result["signal"]:
            reason = result.get("reason", "unknown")
            rejections[reason] = rejections.get(reason, 0) + 1
            continue

        sim = simulate_trade(
            df_4h     = df_4h,
            bar_index = i,
            direction = result["direction"],
            entry     = result["entry"],
            sl        = result["sl"],
            tp1       = result["tp1"],
            tp2       = result["tp2"],
        )

        if sim["outcome"] == "timeout":
            continue

        trades.append({
            "date":      str(df_4h.index[i].date()),
            "coin":      coin,
            "direction": result["direction"],
            "entry":     result["entry"],
            "sl":        result["sl"],
            "tp1":       result["tp1"],
            "exit":      sim["exit_price"],
            "outcome":   sim["outcome"],
            "pnl_r":     sim["pnl_r"],
            "tp1_hit":   sim["tp1_hit"],
            "adx":       result["adx"],
            "rsi":       result["rsi"],
            "vol":       result["vol"],
            "atr_pct":   result["atr_pct"],
        })

    if not trades:
        return {
            "coin":           coin,
            "config":         config,
            "total_signals":  0,
            "wins":           0,
            "losses":         0,
            "win_rate":       0.0,
            "profit_factor":  0.0,
            "avg_rr":         0.0,
            "total_r":        0.0,
            "rejections":     rejections,
            "trades":         [],
        }

    wins     = [t for t in trades if t["outcome"] == "win"]
    losses   = [t for t in trades if t["outcome"] == "loss"]
    total    = len(trades)
    win_rate = round(len(wins) / total * 100, 1) if total > 0 else 0

    gross_p = sum(t["pnl_r"] for t in wins)
    gross_l = abs(sum(t["pnl_r"] for t in losses))
    pf      = round(gross_p / gross_l, 2) if gross_l > 0 else 0.0
    avg_rr  = round(sum(t["pnl_r"] for t in trades) / total, 2) if total > 0 else 0.0
    total_r = round(sum(t["pnl_r"] for t in trades), 2)

    return {
        "coin":          coin,
        "config":        config,
        "total_signals": total,
        "wins":          len(wins),
        "losses":        len(losses),
        "win_rate":      win_rate,
        "profit_factor": pf,
        "avg_rr":        avg_rr,
        "total_r":       total_r,
        "rejections":    rejections,
        "trades":        trades,
    }