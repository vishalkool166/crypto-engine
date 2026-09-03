import numpy as np
import pandas as pd
import logging
import ta

log = logging.getLogger(__name__)


def prepare_indicators(df_4h: pd.DataFrame, df_1h: pd.DataFrame = None) -> pd.DataFrame:
    log.info("    Calculating indicators for %s candles...", len(df_4h))

    df = df_4h.copy()

    close  = df["close"]
    high   = df["high"]
    low    = df["low"]
    volume = df["volume"]

    log.info("    Computing EMAs...")
    df["ema20"]  = ta.trend.ema_indicator(close, window=20)
    df["ema50"]  = ta.trend.ema_indicator(close, window=50)
    df["ema200"] = ta.trend.ema_indicator(close, window=200)

    log.info("    Computing ADX...")
    df["adx"] = ta.trend.adx(high, low, close, window=14)

    log.info("    Computing ATR...")
    df["atr"] = ta.volatility.average_true_range(high, low, close, window=14)

    log.info("    Computing RSI on 4h...")
    df["rsi_4h"] = ta.momentum.rsi(close, window=14)

    log.info("    Computing Volume ratio...")
    df["vol_ma20"]  = volume.rolling(20).mean()
    df["vol_ratio"] = df["vol_ma20"].apply(
        lambda x: 0.0 if pd.isna(x) or x == 0 else 1.0
    )
    df["vol_ratio"] = volume / df["vol_ma20"].replace(0, np.nan)
    df["vol_ratio"] = df["vol_ratio"].fillna(1.0)

    log.info("    Computing ATR pct...")
    df["atr_pct"] = (df["atr"] / close * 100).fillna(0.0)

    log.info("    Computing swing highs/lows...")
    df["swing_high"] = _rolling_swing_high(df, lookback=50)
    df["swing_low"]  = _rolling_swing_low(df,  lookback=50)

    if df_1h is not None and len(df_1h) >= 50:
        log.info("    Computing RSI on 1h and merging...")
        rsi_1h = ta.momentum.rsi(df_1h["close"], window=14)
        rsi_1h_df = rsi_1h.rename("rsi_1h").to_frame()
        rsi_1h_df.index = pd.to_datetime(rsi_1h_df.index, utc=True)
        df.index = pd.to_datetime(df.index, utc=True)
        df = df.merge(
            rsi_1h_df,
            left_index  = True,
            right_index = True,
            how         = "left",
        )
        df["rsi"] = df["rsi_1h"].fillna(df["rsi_4h"])
        log.info("    1h RSI merged successfully")
    else:
        df["rsi"] = df["rsi_4h"]
        log.info("    Using 4h RSI (no 1h data)")

    df = df.dropna(subset=["ema200", "adx", "atr", "rsi"])
    df = df.iloc[220:]

    log.info("    Indicators ready — %s usable bars", len(df))
    return df


def _rolling_swing_high(df: pd.DataFrame, lookback: int = 50) -> pd.Series:
    return df["high"].rolling(window=lookback, min_periods=lookback).max()


def _rolling_swing_low(df: pd.DataFrame, lookback: int = 50) -> pd.Series:
    return df["low"].rolling(window=lookback, min_periods=lookback).min()


def apply_filters_vectorized(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    adx_min      = config["adx_min"]
    rsi_max_long = config["rsi_max_long"]
    atr_pct_max  = config["atr_pct_max"]
    vol_min      = config["vol_min"]

    price  = df["close"].values
    ema20  = df["ema20"].values
    ema50  = df["ema50"].values
    ema200 = df["ema200"].values
    adx    = df["adx"].values
    atr    = df["atr"].values
    atr_pct= df["atr_pct"].values
    rsi    = df["rsi"].values
    vol    = df["vol_ratio"].values
    s_high = df["swing_high"].values
    s_low  = df["swing_low"].values

    not_volatile = atr_pct <= atr_pct_max
    adx_ok       = adx >= adx_min
    vol_ok       = vol >= vol_min

    long_direction  = price > ema200
    short_direction = price < ema200

    buffer     = atr * 0.05
    long_ema   = ((price > ema20 + buffer) & (ema20 > ema50)) | (price > ema20 + buffer * 2)
    short_ema  = ((price < ema20 - buffer) & (ema20 < ema50)) | (price < ema20 - buffer * 2)

    rsi_long_ok  = rsi <= rsi_max_long
    rsi_short_ok = rsi >= (100 - rsi_max_long)

    sl_buffer   = atr * 0.5
    sl_long     = s_low  - sl_buffer
    sl_short    = s_high + sl_buffer

    sl_long_dist  = np.abs(price - sl_long)
    sl_short_dist = np.abs(price - sl_short)

    sl_long_pct  = np.where(price > 0, sl_long_dist  / price * 100, 0)
    sl_short_pct = np.where(price > 0, sl_short_dist / price * 100, 0)

    sl_long_valid  = (sl_long_pct  >= 0.3) & (sl_long_pct  <= 5.0) & (sl_long  < price)
    sl_short_valid = (sl_short_pct >= 0.3) & (sl_short_pct <= 5.0) & (sl_short > price)

    long_signal = (
        not_volatile &
        adx_ok       &
        vol_ok       &
        long_direction &
        long_ema     &
        rsi_long_ok  &
        sl_long_valid
    )

    short_signal = (
        not_volatile  &
        adx_ok        &
        vol_ok        &
        short_direction &
        short_ema     &
        rsi_short_ok  &
        sl_short_valid
    )

    result = df.copy()
    result["signal"]    = np.where(long_signal, "LONG", np.where(short_signal, "SHORT", ""))
    result["sl"]        = np.where(long_signal, sl_long,  np.where(short_signal, sl_short,  0.0))
    result["sl_pct"]    = np.where(long_signal, sl_long_pct, np.where(short_signal, sl_short_pct, 0.0))
    result["tp1"]       = np.where(
        long_signal,
        price + sl_long_dist  * 2.5,
        np.where(short_signal, price - sl_short_dist * 2.5, 0.0)
    )
    result["tp2"]       = np.where(
        long_signal,
        price + sl_long_dist  * 4.0,
        np.where(short_signal, price - sl_short_dist * 4.0, 0.0)
    )

    signals_only = result[result["signal"] != ""].copy()
    return signals_only


def simulate_trades_vectorized(
    signals_df: pd.DataFrame,
    full_df:    pd.DataFrame,
) -> list:
    if signals_df.empty:
        return []

    trades     = []
    full_high  = full_df["high"].values
    full_low   = full_df["low"].values
    full_close = full_df["close"].values
    full_index = list(full_df.index)

    for _, row in signals_df.iterrows():
        try:
            bar_idx   = full_index.index(row.name)
        except ValueError:
            continue

        direction = row["signal"]
        entry     = float(row["close"])
        sl        = float(row["sl"])
        tp1       = float(row["tp1"])
        tp2       = float(row["tp2"])
        is_long   = direction == "LONG"

        future_high  = full_high [bar_idx:bar_idx + 60]
        future_low   = full_low  [bar_idx:bar_idx + 60]
        future_close = full_close[bar_idx:bar_idx + 60]

        if len(future_high) < 2:
            continue

        sl_dist  = abs(entry - sl)
        outcome  = None
        exit_p   = entry
        tp1_hit  = False
        pnl_r    = 0.0

        for j in range(len(future_high)):
            h = future_high[j]
            l = future_low[j]

            if not tp1_hit:
                sl_hit  = (l <= sl)  if is_long else (h >= sl)
                tp1_now = (h >= tp1) if is_long else (l <= tp1)

                if sl_hit and tp1_now:
                    outcome = "loss"
                    exit_p  = sl
                    pnl_r   = -1.0
                    break
                if sl_hit:
                    outcome = "loss"
                    exit_p  = sl
                    pnl_r   = -1.0
                    break
                if tp1_now:
                    tp1_hit = True
                    sl      = entry
                    tp2_now = (h >= tp2) if is_long else (l <= tp2)
                    if tp2_now:
                        outcome = "win"
                        exit_p  = tp2
                        pnl_r   = 4.0
                        break
                    continue
            else:
                tp2_now = (h >= tp2) if is_long else (l <= tp2)
                sl_be   = (l <= sl)  if is_long else (h >= sl)

                if tp2_now:
                    outcome = "win"
                    exit_p  = tp2
                    pnl_r   = 4.0
                    break
                if sl_be:
                    outcome = "win"
                    exit_p  = entry
                    pnl_r   = 0.0
                    break

        if outcome is None:
            if tp1_hit:
                last_close = future_close[-1]
                pnl_r      = round(
                    (last_close - entry) / sl_dist if is_long
                    else (entry - last_close) / sl_dist,
                    2
                )
                outcome = "win"
                exit_p  = last_close
            else:
                continue

        trades.append({
            "date":      str(row.name.date()) if hasattr(row.name, "date") else str(row.name),
            "direction": direction,
            "entry":     round(entry,  6),
            "sl":        round(sl,     6),
            "tp1":       round(tp1,    6),
            "exit":      round(exit_p, 6),
            "outcome":   outcome,
            "pnl_r":     round(pnl_r,  2),
            "tp1_hit":   tp1_hit,
            "adx":       round(float(row["adx"]),     2),
            "rsi":       round(float(row["rsi"]),     2),
            "vol":       round(float(row["vol_ratio"]),2),
            "atr_pct":   round(float(row["atr_pct"]), 2),
        })

    return trades


def calculate_stats(trades: list, config: dict, coin: str) -> dict:
    if not trades:
        return {
            "coin":          coin,
            "config":        config,
            "total_signals": 0,
            "wins":          0,
            "losses":        0,
            "win_rate":      0.0,
            "profit_factor": 0.0,
            "avg_rr":        0.0,
            "total_r":       0.0,
            "score":         -1.0,
        }

    wins   = [t for t in trades if t["outcome"] == "win"]
    losses = [t for t in trades if t["outcome"] == "loss"]
    total  = len(trades)

    win_rate = round(len(wins) / total * 100, 1) if total > 0 else 0.0
    gross_p  = sum(t["pnl_r"] for t in wins)
    gross_l  = abs(sum(t["pnl_r"] for t in losses))
    pf       = round(gross_p / gross_l, 2) if gross_l > 0 else 0.0
    avg_rr   = round(sum(t["pnl_r"] for t in trades) / total, 2) if total > 0 else 0.0
    total_r  = round(sum(t["pnl_r"] for t in trades), 2)

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
        "trades":        trades,
    }


def run_backtest(
    df_4h:      pd.DataFrame,
    df_1h:      pd.DataFrame,
    config:     dict,
    coin:       str = "",
    prepped_df: pd.DataFrame = None,
) -> dict:
    if prepped_df is None:
        log.error("prepped_df is required — call prepare_indicators first")
        return {"error": "prepped_df required"}

    signals_df = apply_filters_vectorized(prepped_df, config)
    trades     = simulate_trades_vectorized(signals_df, prepped_df)
    return calculate_stats(trades, config, coin)