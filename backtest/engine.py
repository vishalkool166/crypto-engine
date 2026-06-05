import pandas as pd
import logging
from data.store import load_candles
from engines.indicators import calculate_all
from engines.regime import detect_regime
from engines.sweep import detect_sweep
from engines.displacement import detect_displacement
from engines.retest import detect_retest
from engines.confluence import score_confluence
from engines.signal import (
    get_session, run_no_trade_engine,
    generate_signal
)
from config import cfg

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# ALIGN WINDOW
# strict timestamp filtering
# no future data leakage
# ═══════════════════════════════════════════════════════
def _align_window(
    df:         pd.DataFrame,
    current_ts: pd.Timestamp,
    window:     int
) -> pd.DataFrame:
    aligned = df[df.index < current_ts].copy()
    if len(aligned) < window:
        return aligned
    return aligned.iloc[-window:]


# ═══════════════════════════════════════════════════════
# SIMULATE TRADE ON 4H CANDLES
# checks SL and TP on each 4H candle
# determines which hit first
# much more accurate than daily
# ═══════════════════════════════════════════════════════
def _simulate_trade_4h(
    df_4h:     pd.DataFrame,
    current_ts: pd.Timestamp,
    direction: str,
    entry:     float,
    sl:        float,
    tp1:       float,
    tp2:       float,
    max_candles: int = 120  # 120 x 4H = 20 days max
) -> dict:
    """
    Simulates trade outcome using 4H candles.
    Checks SL before TP on each candle.
    Returns outcome dict with exit details.
    """

    # Get future 4H candles after entry
    future = df_4h[
        df_4h.index > current_ts
    ].head(max_candles)

    if len(future) < 2:
        return {
            "outcome":     "timeout",
            "exit_price":  entry,
            "exit_candle": 0,
            "candles":     0,
            "reason":      "Not enough future data"
        }

    tp1_hit = False

    for j, (ts, c) in enumerate(future.iterrows()):
        h = float(c["high"])
        l = float(c["low"])
        o = float(c["open"])
        cl = float(c["close"])

        if direction == "LONG":

            # ── LONG TRADE ──
            # Check SL first — worst case scenario
            # If both SL and TP in same candle
            # assume SL hit first (conservative)

            if not tp1_hit:
                # Phase 1 — looking for TP1 or SL
                if l <= sl and h >= tp1:
                    # Both in same candle
                    # Check open price for direction
                    if o <= sl:
                        # Opened below SL — gapped down
                        return {
                            "outcome":     "loss",
                            "exit_price":  sl,
                            "exit_candle": j,
                            "candles":     j + 1,
                            "reason":      "SL gap down"
                        }
                    else:
                        # Assume SL hit first
                        # conservative approach
                        return {
                            "outcome":     "loss",
                            "exit_price":  sl,
                            "exit_candle": j,
                            "candles":     j + 1,
                            "reason":      "SL before TP1"
                        }

                elif l <= sl:
                    # SL hit
                    return {
                        "outcome":     "loss",
                        "exit_price":  sl,
                        "exit_candle": j,
                        "candles":     j + 1,
                        "reason":      "SL hit"
                    }

                elif h >= tp1:
                    # TP1 hit — move SL to breakeven
                    tp1_hit = True
                    # Continue to TP2 with BE SL
                    sl = entry  # breakeven
                    continue

            else:
                # Phase 2 — TP1 hit, running to TP2
                # SL now at breakeven

                if l <= sl:
                    # Stopped at breakeven
                    return {
                        "outcome":     "win",
                        "exit_price":  entry,
                        "exit_candle": j,
                        "candles":     j + 1,
                        "reason":      "TP1 + BE stop",
                        "tp1_hit":     True
                    }

                elif h >= tp2:
                    # TP2 hit — full win
                    return {
                        "outcome":     "win",
                        "exit_price":  tp2,
                        "exit_candle": j,
                        "candles":     j + 1,
                        "reason":      "TP2 hit",
                        "tp1_hit":     True,
                        "tp2_hit":     True
                    }

        else:
            # ── SHORT TRADE ──

            if not tp1_hit:
                # Phase 1 — looking for TP1 or SL
                if h >= sl and l <= tp1:
                    # Both in same candle
                    if o >= sl:
                        # Opened above SL — gapped up
                        return {
                            "outcome":     "loss",
                            "exit_price":  sl,
                            "exit_candle": j,
                            "candles":     j + 1,
                            "reason":      "SL gap up"
                        }
                    else:
                        # Assume SL hit first
                        return {
                            "outcome":     "loss",
                            "exit_price":  sl,
                            "exit_candle": j,
                            "candles":     j + 1,
                            "reason":      "SL before TP1"
                        }

                elif h >= sl:
                    # SL hit
                    return {
                        "outcome":     "loss",
                        "exit_price":  sl,
                        "exit_candle": j,
                        "candles":     j + 1,
                        "reason":      "SL hit"
                    }

                elif l <= tp1:
                    # TP1 hit — move SL to breakeven
                    tp1_hit = True
                    sl = entry  # breakeven
                    continue

            else:
                # Phase 2 — TP1 hit, running to TP2

                if h >= sl:
                    # Stopped at breakeven
                    return {
                        "outcome":     "win",
                        "exit_price":  entry,
                        "exit_candle": j,
                        "candles":     j + 1,
                        "reason":      "TP1 + BE stop",
                        "tp1_hit":     True
                    }

                elif l <= tp2:
                    # TP2 hit — full win
                    return {
                        "outcome":     "win",
                        "exit_price":  tp2,
                        "exit_candle": j,
                        "candles":     j + 1,
                        "reason":      "TP2 hit",
                        "tp1_hit":     True,
                        "tp2_hit":     True
                    }

    # Timeout — neither hit in max candles
    last_close = float(future.iloc[-1]["close"])
    return {
        "outcome":     "timeout",
        "exit_price":  last_close,
        "exit_candle": len(future),
        "candles":     len(future),
        "reason":      f"Timeout {len(future)} candles"
    }


# ═══════════════════════════════════════════════════════
# CALCULATE PNL
# accounts for fees on both entry and exit
# ═══════════════════════════════════════════════════════
def _calculate_pnl(
    direction:  str,
    entry:      float,
    exit_price: float,
    pos_size:   float,
    outcome:    str
) -> float:
    """
    Calculates realistic PnL including fees.
    Binance futures taker fee: 0.06% each side.
    """
    TAKER_FEE = 0.0006

    if direction == "LONG":
        gross_pnl = (
            (exit_price - entry) / entry * pos_size
        )
    else:
        gross_pnl = (
            (entry - exit_price) / entry * pos_size
        )

    # Deduct fees both sides
    entry_fee = pos_size * TAKER_FEE
    exit_fee  = pos_size * TAKER_FEE
    total_fee = entry_fee + exit_fee

    net_pnl = gross_pnl - total_fee

    return round(net_pnl, 4)


# ═══════════════════════════════════════════════════════
# RUN BACKTEST
# walk forward — no future leakage
# 4H simulation — accurate SL/TP detection
# ═══════════════════════════════════════════════════════
def run_backtest(
    coin:     str,
    capital:  float = cfg.CAPITAL,
    leverage: int   = cfg.LEVERAGE,
    window:   int   = 200
) -> dict:

    log.info(f"Starting backtest: {coin}")

    # ── LOAD ALL TIMEFRAMES ──
    df_1d = load_candles(coin, "1d", limit=1000)
    df_4h = load_candles(coin, "4h", limit=2000)
    df_1h = load_candles(coin, "1h", limit=2000)
    df_1w = load_candles(coin, "1w", limit=500)

    # ── VALIDATE DATA ──
    if df_1d is None or len(df_1d) < window + 50:
        return {
            "error": (
                f"Not enough 1D data for {coin}. "
                f"Have {len(df_1d) if df_1d is not None else 0}"
                f" candles, need {window + 50}. "
                f"Run app first to download history."
            )
        }

    if df_4h is None or len(df_4h) < 200:
        return {
            "error": (
                f"Not enough 4H data for {coin}. "
                f"Need 200+ candles."
            )
        }

    if df_1h is None or len(df_1h) < 100:
        return {
            "error": f"Not enough 1H data for {coin}."
        }

    if df_1w is None or len(df_1w) < 20:
        return {
            "error": f"Not enough 1W data for {coin}."
        }

    log.info(
        f"Data loaded: {coin} "
        f"1D:{len(df_1d)} "
        f"4H:{len(df_4h)} "
        f"1H:{len(df_1h)} "
        f"1W:{len(df_1w)}"
    )

    trades      = []
    signals_log = []
    equity      = capital
    peak_equity = capital
    skipped     = 0
    in_trade    = False

    # ── WALK FORWARD ──
    for i in range(window, len(df_1d) - 1):

        current_ts = df_1d.index[i]

        # ── ALIGN ALL WINDOWS ──
        d1d_window = df_1d.iloc[i - window:i].copy()

        d4h_window = _align_window(
            df_4h, current_ts, window
        )
        d1h_window = _align_window(
            df_1h, current_ts, window
        )
        d1w_window = _align_window(
            df_1w, current_ts, 100
        )

        # Skip if not enough data
        if (
            len(d4h_window) < 50 or
            len(d1h_window) < 50 or
            len(d1w_window) < 10
        ):
            skipped += 1
            continue

        try:
            # ── CALCULATE INDICATORS ──
            d1d = calculate_all(d1d_window)
            d4h = calculate_all(d4h_window)
            d1h = calculate_all(d1h_window)
            d1w = calculate_all(d1w_window)

            price = d1d["price"]
            if not price or price <= 0:
                continue

            # ── KEY LEVELS ──
            key_levels = {
                "pdh": float(
                    d1d_window.iloc[-2]["high"]
                ) if len(d1d_window) >= 2 else 0,
                "pdl": float(
                    d1d_window.iloc[-2]["low"]
                ) if len(d1d_window) >= 2 else 0,
                "pdc": float(
                    d1d_window.iloc[-2]["close"]
                ) if len(d1d_window) >= 2 else 0,
                "pwh": float(
                    d1w_window.iloc[-2]["high"]
                ) if len(d1w_window) >= 2 else 0,
                "pwl": float(
                    d1w_window.iloc[-2]["low"]
                ) if len(d1w_window) >= 2 else 0,
            }

            # ── MARKET ──
            # Backtest uses price only
            # funding/OI not available historically
            prev_close = float(
                d1d_window.iloc[-2]["close"]
            ) if len(d1d_window) >= 2 else price

            market = {
                "price":       price,
                "change24":    (
                    (price - prev_close) /
                    prev_close * 100
                ) if prev_close > 0 else 0,
                "funding":     0.0,
                "oi":          0.0,
                "oi_change":   0.0,
                "long_ratio":  50.0,
                "short_ratio": 50.0,
                "fear_greed":  {
                    "value": 50,
                    "label": "Neutral"
                }
            }

            oi_matrix = {
                "primary_score":    5,
                "primary_label":    "Neutral",
                "funding_score":    6,
                "funding_warning":  "",
                "crowding_warning": ""
            }

            news_filter = {
                "clear":   True,
                "blocked": False,
                "warning": False,
                "alerts":  []
            }

            btc_inst = {
                "stable":   True,
                "warnings": [],
                "score":    8
            }

            session = get_session()
            regime  = detect_regime(d1d, d4h)

            sweep = detect_sweep(
                d1d_window,
                key_levels,
                d1d.get("atr", 0),
                d1d["swings"]
            )
            disp = detect_displacement(
                d4h_window,
                d4h.get("atr", 0)
            )
            retest = detect_retest(
                d4h_window, d4h,
                sweep, disp
            )

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
                wconf["norm_score"]
            )

            signal = generate_signal(
                d1d, d4h,
                wconf, no_trade,
                market, key_levels,
                equity, leverage
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

            # Only simulate A/A+
            if (
                grade not in ["A+", "A"] or
                direction not in ["LONG", "SHORT"]
            ):
                continue

            entry  = price
            sl     = signal["sl"]
            tp1    = signal["tp1"]
            tp2    = signal["tp2"]

            # Validate levels
            if not sl or not tp1 or not tp2:
                continue

            if direction == "LONG":
                if sl >= entry or tp1 <= entry:
                    continue
            else:
                if sl <= entry or tp1 >= entry:
                    continue

            # ── SIMULATE ON 4H CANDLES ──
            # This is the key improvement
            # 4H candles catch intraday SL hits
            # that daily candles miss
            sim = _simulate_trade_4h(
                df_4h      = df_4h,
                current_ts = current_ts,
                direction  = direction,
                entry      = entry,
                sl         = sl,
                tp1        = tp1,
                tp2        = tp2,
                max_candles = 120  # 20 days max
            )

            outcome    = sim["outcome"]
            exit_price = sim["exit_price"]

            # ── CALCULATE PNL WITH FEES ──
            sl_pct   = abs(entry - sl) / entry
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

            equity     += pnl
            peak_equity = max(peak_equity, equity)
            drawdown    = round(
                (peak_equity - equity) /
                peak_equity * 100, 2
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
                "reason":      sim.get("reason",""),
                "tp1_hit":     sim.get("tp1_hit",False),
                "tp2_hit":     sim.get("tp2_hit",False)
            })

            log.debug(
                f"Trade: {coin} {direction} "
                f"@ {entry:.2f} "
                f"→ {outcome} "
                f"exit:{exit_price:.2f} "
                f"pnl:${pnl} "
                f"reason:{sim.get('reason','')}"
            )

        except Exception as e:
            log.debug(
                f"Backtest candle {i} error: {e}"
            )
            continue

    log.info(
        f"Backtest done: {coin} "
        f"trades:{len(trades)} "
        f"skipped:{skipped} "
        f"final_equity:${equity:.4f}"
    )

    if not trades:
        return {
            "coin":          coin,
            "total_signals": len(signals_log),
            "total_trades":  0,
            "skipped":       skipped,
            "error": (
                "No A/A+ trades generated. "
                "Signal conditions too strict "
                "or not enough history."
            )
        }

    from backtest.report import build_report
    return build_report(
        coin         = coin,
        trades       = trades,
        signals_log  = signals_log,
        capital      = capital,
        final_equity = equity
    )