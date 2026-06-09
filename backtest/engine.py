import pandas as pd
import logging
from data.store import load_candles
from engines.indicators import calculate_all
from engines.regime import detect_regime, assess_btc_stability
from engines.sweep import detect_sweep
from engines.displacement import detect_displacement
from engines.retest import detect_retest
from engines.confluence import score_confluence
from engines.signal import get_session, run_no_trade_engine, generate_signal
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
    tp2:         float,
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
            "reason":      "Not enough future data",
            "tp1_hit":     False,
            "tp2_hit":     False
        }

    for j, (ts, c) in enumerate(future.iterrows()):
        h = float(c["high"])
        l = float(c["low"])
        o = float(c["open"])

        sl_hit      = (l <= sl)  if is_long else (h >= sl)
        tp1_hit_now = (h >= tp1) if is_long else (l <= tp1)
        tp2_hit_now = (h >= tp2) if is_long else (l <= tp2)

        if not tp1_hit:
            both_in_candle = sl_hit and tp1_hit_now

            if both_in_candle:
                gap_sl = (o <= sl) if is_long else (o >= sl)
                return {
                    "outcome":     "loss",
                    "exit_price":  sl,
                    "exit_candle": j,
                    "candles":     j + 1,
                    "reason":      "SL gap" if gap_sl else "SL before TP1",
                    "tp1_hit":     False,
                    "tp2_hit":     False
                }

            if sl_hit:
                return {
                    "outcome":     "loss",
                    "exit_price":  sl,
                    "exit_candle": j,
                    "candles":     j + 1,
                    "reason":      "SL hit",
                    "tp1_hit":     False,
                    "tp2_hit":     False
                }

            if tp1_hit_now:
                tp1_hit = True
                sl      = entry
                continue

        else:
            sl_be_hit = (l <= sl) if is_long else (h >= sl)

            if sl_be_hit:
                return {
                    "outcome":     "win",
                    "exit_price":  entry,
                    "exit_candle": j,
                    "candles":     j + 1,
                    "reason":      "TP1 + BE stop",
                    "tp1_hit":     True,
                    "tp2_hit":     False
                }

            if tp2_hit_now:
                return {
                    "outcome":     "win",
                    "exit_price":  tp2,
                    "exit_candle": j,
                    "candles":     j + 1,
                    "reason":      "TP2 hit",
                    "tp1_hit":     True,
                    "tp2_hit":     True
                }

    last_close = float(future.iloc[-1]["close"])
    return {
        "outcome":     "timeout",
        "exit_price":  last_close,
        "exit_candle": len(future),
        "candles":     len(future),
        "reason":      f"Timeout {len(future)} candles",
        "tp1_hit":     tp1_hit,
        "tp2_hit":     False
    }


def _calculate_pnl(
    direction:  str,
    entry:      float,
    exit_price: float,
    pos_size:   float,
    outcome:    str
) -> float:
    TAKER_FEE = 0.0006

    if direction == "LONG":
        gross_pnl = (exit_price - entry) / entry * pos_size
    else:
        gross_pnl = (entry - exit_price) / entry * pos_size

    total_fee = pos_size * TAKER_FEE * 2
    return round(gross_pnl - total_fee, 4)


def run_backtest(
    coin:     str,
    capital:  float = cfg.CAPITAL,
    leverage: int   = cfg.LEVERAGE,
    window:   int   = 200
) -> dict:

    log.info(f"Starting backtest: {coin}")

    df_1d = load_candles(coin, "1d", limit=1000)
    df_4h = load_candles(coin, "4h", limit=2000)
    df_1h = load_candles(coin, "1h", limit=2000)
    df_1w = load_candles(coin, "1w", limit=500)

    if df_1d is None or len(df_1d) < window + 50:
        return {
            "error": (
                f"Not enough 1D data for {coin}. "
                f"Have {len(df_1d) if df_1d is not None else 0}"
                f" candles, need {window + 50}."
            )
        }
    if df_4h is None or len(df_4h) < 200:
        return {"error": f"Not enough 4H data for {coin}. Need 200+ candles."}
    if df_1h is None or len(df_1h) < 100:
        return {"error": f"Not enough 1H data for {coin}."}
    if df_1w is None or len(df_1w) < 20:
        return {"error": f"Not enough 1W data for {coin}."}

    log.info(f"Data loaded: {coin} 1D:{len(df_1d)} 4H:{len(df_4h)} 1H:{len(df_1h)} 1W:{len(df_1w)}")

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
            d1d = calculate_all(d1d_window)
            d4h = calculate_all(d4h_window)
            d1h = calculate_all(d1h_window)
            d1w = calculate_all(d1w_window)

            price = d1d["price"]
            if not price or price <= 0:
                continue

            key_levels = {
                "pdh": float(d1d_window.iloc[-2]["high"])  if len(d1d_window) >= 2 else 0,
                "pdl": float(d1d_window.iloc[-2]["low"])   if len(d1d_window) >= 2 else 0,
                "pdc": float(d1d_window.iloc[-2]["close"]) if len(d1d_window) >= 2 else 0,
                "pwh": float(d1w_window.iloc[-2]["high"])  if len(d1w_window) >= 2 else 0,
                "pwl": float(d1w_window.iloc[-2]["low"])   if len(d1w_window) >= 2 else 0,
            }

            prev_close = float(d1d_window.iloc[-2]["close"]) if len(d1d_window) >= 2 else price
            market = {
                "price":       price,
                "change24":    (price - prev_close) / prev_close * 100 if prev_close > 0 else 0,
                "funding":     0.0,
                "oi":          0.0,
                "oi_change":   0.0,
                "long_ratio":  50.0,
                "short_ratio": 50.0,
                "fear_greed":  {"value": 50, "label": "Neutral"}
            }

            oi_matrix = {
                "primary_score":    5,
                "primary_label":    "Neutral",
                "funding_score":    6,
                "funding_warning":  "",
                "crowding_warning": ""
            }

            news_filter = {"clear": True, "blocked": False, "warning": False, "alerts": []}
            btc_inst    = assess_btc_stability(d1d)
            session     = get_session()
            regime      = detect_regime(d1d, d4h)

            sweep = detect_sweep(
                d1d_window, key_levels,
                d1d.get("atr", 0), d1d["swings"]
            )
            disp = detect_displacement(d4h_window, d4h.get("atr", 0))
            retest = detect_retest(d4h_window, d4h, sweep, disp)

            wconf = score_confluence(
                d1w, d1d, d4h, d1h,
                market, key_levels,
                session, d1d,
                btc_inst, regime,
                sweep, disp,
                retest, oi_matrix,
                coin
            )

            no_trade = run_no_trade_engine(
                regime, d1d, d4h,
                market, session,
                sweep, disp,
                retest, d1d,
                btc_inst, oi_matrix,
                news_filter,
                wconf["norm_score"],
                coin=coin,
                d1w=d1w
            )

            signal = generate_signal(
                d1d, d4h,
                wconf, no_trade,
                market, key_levels,
                equity, leverage,
                d1w=d1w
            )

            grade     = signal.get("grade")
            direction = signal.get("direction")

            signals_log.append({
                "date":      str(current_ts.date()),
                "grade":     grade,
                "direction": direction,
                "score":     signal.get("score", 0),
                "price":     price
            })

            if grade not in ["A+", "A"] or direction not in ["LONG", "SHORT"]:
                continue

            entry = price
            sl    = signal["sl"]
            tp1   = signal["tp1"]
            tp2   = signal["tp2"]

            if not sl or not tp1 or not tp2:
                continue

            if direction == "LONG":
                if sl >= entry or tp1 <= entry:
                    continue
            else:
                if sl <= entry or tp1 >= entry:
                    continue

            sim = _simulate_trade_4h(
                df_4h       = df_4h,
                current_ts  = current_ts,
                direction   = direction,
                entry       = entry,
                sl          = sl,
                tp1         = tp1,
                tp2         = tp2,
                max_candles = 120
            )

            outcome    = sim["outcome"]
            exit_price = sim["exit_price"]

            sl_pct = abs(entry - sl) / entry
            if sl_pct <= 0:
                continue

            risk_amt = equity * cfg.RISK_PCT_PER_TRADE
            pos_size = risk_amt / sl_pct

            pnl = _calculate_pnl(
                direction  = direction,
                entry      = entry,
                exit_price = exit_price,
                pos_size   = pos_size,
                outcome    = outcome
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
                "score":       signal.get("score", 0),
                "entry":       round(entry, 6),
                "sl":          round(sl, 6),
                "tp1":         round(tp1, 6),
                "tp2":         round(tp2, 6),
                "exit_price":  round(exit_price, 6),
                "outcome":     outcome,
                "pnl":         pnl,
                "equity":      round(equity, 4),
                "drawdown":    drawdown,
                "exit_candle": sim.get("exit_candle"),
                "candles":     sim.get("candles"),
                "reason":      sim.get("reason", ""),
                "tp1_hit":     sim.get("tp1_hit", False),
                "tp2_hit":     sim.get("tp2_hit", False),
                "regime":      regime.get("label", ""),
                "session":     session.get("name", "")
            })

            log.debug(
                f"Trade: {coin} {direction} @ {entry:.2f} "
                f"→ {outcome} exit:{exit_price:.2f} "
                f"pnl:${pnl} reason:{sim.get('reason','')}"
            )

        except Exception as e:
            log.debug(f"Backtest candle {i} error: {e}")
            continue

    log.info(
        f"Backtest done: {coin} trades:{len(trades)} "
        f"skipped:{skipped} final_equity:${equity:.4f}"
    )

    if not trades:
        return {
            "coin":          coin,
            "total_signals": len(signals_log),
            "total_trades":  0,
            "skipped":       skipped,
            "error":         "No A/A+ trades generated."
        }

    from backtest.report import build_report
    return build_report(
        coin         = coin,
        trades       = trades,
        signals_log  = signals_log,
        capital      = capital,
        final_equity = equity
    )