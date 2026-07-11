import pandas as pd
import logging
from data.store import load_candles
from engines.indicators import calculate_all
from engines.sweep import detect_sweep
from engines.displacement import detect_displacement
from engines.bias import get_htf_bias
from engines.zone_finder import get_active_zone
from engines.signal_core import build_signal, validate_risk
from config import cfg

log = logging.getLogger(__name__)


def _align_window(
    df:         pd.DataFrame,
    current_ts: pd.Timestamp,
    window:     int
) -> pd.DataFrame:
    aligned = df[df.index < current_ts].copy()
    if len(aligned) < window:
        return aligned
    return aligned.iloc[-window:]


def _simulate_trade_4h(
    df_4h:       pd.DataFrame,
    current_ts:  pd.Timestamp,
    direction:   str,
    entry:       float,
    sl:          float,
    tp1:         float,
    max_candles: int = 120
) -> dict:
    future  = df_4h[df_4h.index > current_ts].head(max_candles)
    is_long = direction == "LONG"
    tp1_hit = False

    if len(future) < 2:
        return {
            "outcome":     "timeout",
            "exit_price":  entry,
            "exit_candle": 0,
            "candles":     0,
            "reason":      "insufficient_future_data",
            "tp1_hit":     False,
        }

    for j, (ts, c) in enumerate(future.iterrows()):
        h = float(c["high"])
        l = float(c["low"])
        o = float(c["open"])

        sl_hit      = (l <= sl)  if is_long else (h >= sl)
        tp1_hit_now = (h >= tp1) if is_long else (l <= tp1)

        if not tp1_hit:
            if sl_hit and tp1_hit_now:
                gap_sl = (o <= sl) if is_long else (o >= sl)
                return {
                    "outcome":     "loss",
                    "exit_price":  sl,
                    "exit_candle": j,
                    "candles":     j + 1,
                    "reason":      "sl_gap" if gap_sl else "sl_before_tp1",
                    "tp1_hit":     False,
                }
            if sl_hit:
                return {
                    "outcome":     "loss",
                    "exit_price":  sl,
                    "exit_candle": j,
                    "candles":     j + 1,
                    "reason":      "sl_hit",
                    "tp1_hit":     False,
                }
            if tp1_hit_now:
                tp1_hit = True
                sl      = entry
                continue
        else:
            if (l <= sl) if is_long else (h >= sl):
                return {
                    "outcome":     "win",
                    "exit_price":  entry,
                    "exit_candle": j,
                    "candles":     j + 1,
                    "reason":      "tp1_be_stop",
                    "tp1_hit":     True,
                }

    last_close = float(future.iloc[-1]["close"])
    return {
        "outcome":     "timeout",
        "exit_price":  last_close,
        "exit_candle": len(future),
        "candles":     len(future),
        "reason":      f"timeout_{len(future)}_candles",
        "tp1_hit":     tp1_hit,
    }


def _calculate_pnl(
    direction:  str,
    entry:      float,
    exit_price: float,
    pos_size:   float,
) -> float:
    from config import TAKER_FEE
    if direction == "LONG":
        gross = (exit_price - entry) / entry * pos_size
    else:
        gross = (entry - exit_price) / entry * pos_size
    return round(gross - pos_size * TAKER_FEE * 2, 4)


def run_backtest(
    coin:     str,
    capital:  float = 1000.0,
    leverage: int   = 10,
    window:   int   = 200
) -> dict:
    log.info("Backtest started: %s", coin)

    df_1d = load_candles(coin, "1d", limit=1000)
    df_4h = load_candles(coin, "4h", limit=2000)
    df_1h = load_candles(coin, "1h", limit=2000)
    df_1w = load_candles(coin, "1w", limit=500)

    if df_1d is None or len(df_1d) < window + 50:
        return {"error": f"Insufficient 1D data: {coin}"}
    if df_4h is None or len(df_4h) < 200:
        return {"error": f"Insufficient 4H data: {coin}"}
    if df_1h is None or len(df_1h) < 100:
        return {"error": f"Insufficient 1H data: {coin}"}
    if df_1w is None or len(df_1w) < 20:
        return {"error": f"Insufficient 1W data: {coin}"}

    is_btc    = coin == "BTC"
    df_btc_1d = None if is_btc else load_candles("BTC", "1d", limit=1000)
    df_btc_4h = None if is_btc else load_candles("BTC", "4h", limit=2000)

    trades      = []
    signals_log = []
    equity      = capital
    peak_equity = capital
    skipped     = 0

    for i in range(window, len(df_1d) - 1):
        current_ts = df_1d.index[i]

        d1d_window = df_1d.iloc[i - window:i].copy()
        d4h_window = _align_window(df_4h, current_ts, window)
        d1h_window = _align_window(df_1h, current_ts, window)
        d1w_window = _align_window(df_1w, current_ts, 100)

        if len(d4h_window) < 50 or len(d1h_window) < 50 or len(d1w_window) < 10:
            skipped += 1
            continue

        try:
            d1d = calculate_all(d1d_window, timeframe="1d")
            d4h = calculate_all(d4h_window, timeframe="4h")
            d1h = calculate_all(d1h_window, timeframe="1h")
            d1w = calculate_all(d1w_window, timeframe="1w")

            price = d1d.get("price", 0)
            if not price or price <= 0:
                continue

            key_levels = {
                "pdh": float(d1d_window.iloc[-2]["high"])  if len(d1d_window) >= 2 else 0,
                "pdl": float(d1d_window.iloc[-2]["low"])   if len(d1d_window) >= 2 else 0,
                "pdc": float(d1d_window.iloc[-2]["close"]) if len(d1d_window) >= 2 else 0,
                "pwh": float(d1w_window.iloc[-2]["high"])  if len(d1w_window) >= 2 else 0,
                "pwl": float(d1w_window.iloc[-2]["low"])   if len(d1w_window) >= 2 else 0,
            }

            bias = get_htf_bias(d1w, d1d, d1d_window, key_levels)

            signals_log.append({
                "date":      str(current_ts.date()),
                "bias":      bias.get("direction", "NONE"),
                "strength":  bias.get("strength", "none"),
                "reason":    bias.get("no_bias_reason", ""),
                "price":     price,
            })

            if not bias["valid"]:
                continue

            zone = get_active_zone(d4h, bias["direction"])
            if not zone:
                continue

            risk = validate_risk(
                entry     = price,
                zone      = zone,
                direction = bias["direction"],
                d4h       = d4h,
            )

            if not risk["valid"]:
                continue

            context = {
                "direction":       bias["direction"],
                "bias":            bias,
                "zone":            zone,
                "trigger_pattern": "backtest_bar",
                "entry_price":     price,
                "candle_low":      float(d1d_window.iloc[-1]["low"]),
                "candle_high":     float(d1d_window.iloc[-1]["high"]),
                "sl":              risk["sl"],
                "tp1":             risk["tp1"],
                "rr":              risk["rr"],
                "rr_valid":        True,
            }

            signal = build_signal(coin, context, d1h, d4h)
            if not signal:
                continue

            grade     = signal.get("grade")
            direction = signal.get("direction")
            entry     = price
            sl        = signal.get("sl")
            tp1       = signal.get("tp1")

            if grade not in ("A+", "A") or direction not in ("LONG", "SHORT"):
                continue
            if not sl or not tp1:
                continue
            if direction == "LONG"  and (sl >= entry or tp1 <= entry):
                continue
            if direction == "SHORT" and (sl <= entry or tp1 >= entry):
                continue

            sim = _simulate_trade_4h(
                df_4h      = df_4h,
                current_ts = current_ts,
                direction  = direction,
                entry      = entry,
                sl         = sl,
                tp1        = tp1,
            )

            sl_pct = abs(entry - sl) / entry
            if sl_pct <= 0:
                continue

            risk_amt = equity * cfg.RISK_PCT_PER_TRADE
            pos_size = risk_amt / sl_pct

            pnl = _calculate_pnl(
                direction  = direction,
                entry      = entry,
                exit_price = sim["exit_price"],
                pos_size   = pos_size,
            )

            equity      += pnl
            peak_equity  = max(peak_equity, equity)
            drawdown     = round(
                (peak_equity - equity) / peak_equity * 100, 2
            ) if peak_equity > 0 else 0

            trades.append({
                "date":        str(current_ts.date()),
                "coin":        coin,
                "grade":       grade,
                "direction":   direction,
                "entry":       round(entry, 6),
                "sl":          round(sl, 6),
                "tp1":         round(tp1, 6),
                "exit_price":  round(sim["exit_price"], 6),
                "outcome":     sim["outcome"],
                "pnl":         pnl,
                "equity":      round(equity, 4),
                "drawdown":    drawdown,
                "exit_candle": sim.get("exit_candle"),
                "candles":     sim.get("candles"),
                "reason":      sim.get("reason", ""),
                "tp1_hit":     sim.get("tp1_hit", False),
                "bias_strength": bias.get("strength", ""),
                "zone_type":   zone.get("type", ""),
                "sweep_age_h": bias.get("sweep_age_hours", 0),
            })

        except Exception as e:
            log.debug("Backtest candle %s error: %s", i, e)
            continue

    log.info(
        "Backtest complete: %s trades:%s skipped:%s equity:$%.2f",
        coin, len(trades), skipped, equity
    )

    if not trades:
        return {
            "coin":          coin,
            "total_signals": len(signals_log),
            "total_trades":  0,
            "skipped":       skipped,
            "error":         "No A/A+ trades generated",
        }

    from backtest.report import build_report
    return build_report(
        coin         = coin,
        trades       = trades,
        signals_log  = signals_log,
        capital      = capital,
        final_equity = equity,
    )