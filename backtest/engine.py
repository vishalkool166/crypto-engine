import pandas as pd
import logging
from data.store import load_candles
from engines.indicators import calculate_all
from engines.regime.detector import detect as detect_regime
from engines.trend.direction import detect as detect_trend
from engines.reversion.timing import detect as detect_reversion
from engines.ict.confirmation import confirm as confirm_ict
from engines.risk.calculator import calculate as calculate_risk
from config import cfg, TAKER_FEE

log = logging.getLogger(__name__)

WINDOW_4H  = 200
WINDOW_1H  = 300
WINDOW_15M = 200

HE = cfg.HYBRID_ENGINE


def _align_window(
    df:         pd.DataFrame,
    current_ts: pd.Timestamp,
    window:     int,
) -> pd.DataFrame:
    aligned = df[df.index < current_ts].copy()
    if len(aligned) < window:
        return aligned
    return aligned.iloc[-window:]


def _simulate_trade(
    df_4h:      pd.DataFrame,
    current_ts: pd.Timestamp,
    direction:  str,
    entry:      float,
    sl:         float,
    tp1:        float,
    tp2:        float | None,
) -> dict:
    future  = df_4h[df_4h.index > current_ts].head(120)
    is_long = direction == "LONG"
    tp1_hit = False

    if len(future) < 2:
        return {
            "outcome":    "timeout",
            "exit_price": entry,
            "candles":    0,
            "close_ts":   current_ts,
            "reason":     "insufficient_future_data",
            "tp1_hit":    False,
            "tp2_hit":    False,
        }

    for j, (ts, c) in enumerate(future.iterrows()):
        h = float(c["high"])
        l = float(c["low"])

        sl_hit  = (l <= sl)  if is_long else (h >= sl)
        tp1_now = (h >= tp1) if is_long else (l <= tp1)
        tp2_now = tp2 and ((h >= tp2) if is_long else (l <= tp2))

        if not tp1_hit:
            if sl_hit and tp1_now:
                return {
                    "outcome":    "loss",
                    "exit_price": sl,
                    "candles":    j + 1,
                    "close_ts":   ts,
                    "reason":     "sl_gap",
                    "tp1_hit":    False,
                    "tp2_hit":    False,
                }
            if sl_hit:
                return {
                    "outcome":    "loss",
                    "exit_price": sl,
                    "candles":    j + 1,
                    "close_ts":   ts,
                    "reason":     "sl_hit",
                    "tp1_hit":    False,
                    "tp2_hit":    False,
                }
            if tp1_now:
                tp1_hit = True
                sl      = entry
                if not tp2:
                    return {
                        "outcome":    "win",
                        "exit_price": tp1,
                        "candles":    j + 1,
                        "close_ts":   ts,
                        "reason":     "tp1_hit",
                        "tp1_hit":    True,
                        "tp2_hit":    False,
                    }
                continue
        else:
            if tp2_now:
                return {
                    "outcome":    "win",
                    "exit_price": tp2,
                    "candles":    j + 1,
                    "close_ts":   ts,
                    "reason":     "tp2_hit",
                    "tp1_hit":    True,
                    "tp2_hit":    True,
                }
            if (l <= sl) if is_long else (h >= sl):
                return {
                    "outcome":    "win",
                    "exit_price": entry,
                    "candles":    j + 1,
                    "close_ts":   ts,
                    "reason":     "tp1_be_stop",
                    "tp1_hit":    True,
                    "tp2_hit":    False,
                }

    last_close = float(future.iloc[-1]["close"])
    close_ts   = future.index[-1]
    outcome    = "win" if tp1_hit else "timeout"
    return {
        "outcome":    outcome,
        "exit_price": last_close,
        "candles":    len(future),
        "close_ts":   close_ts,
        "reason":     f"timeout_{len(future)}_candles",
        "tp1_hit":    tp1_hit,
        "tp2_hit":    False,
    }


def _calculate_pnl(
    direction:  str,
    entry:      float,
    exit_price: float,
    pos_size:   float,
    tp1_hit:    bool,
    tp2_hit:    bool,
    tp1:        float,
    tp2:        float | None,
) -> float:
    tp1_pct  = HE["tp1_close_pct"]
    tp2_pct  = HE["tp2_close_pct"]
    fee_mult = TAKER_FEE * 2
    slippage = 0.0005

    if direction == "LONG":
        entry      = entry      * (1 + slippage)
        exit_price = exit_price * (1 - slippage)
        if tp1: tp1 = tp1 * (1 - slippage)
        if tp2: tp2 = tp2 * (1 - slippage)
    else:
        entry      = entry      * (1 - slippage)
        exit_price = exit_price * (1 + slippage)
        if tp1: tp1 = tp1 * (1 + slippage)
        if tp2: tp2 = tp2 * (1 + slippage)

    if tp2_hit and tp2:
        if direction == "LONG":
            gross = (
                (tp1 - entry) / entry * pos_size * tp1_pct +
                (tp2 - entry) / entry * pos_size * tp2_pct
            )
        else:
            gross = (
                (entry - tp1) / entry * pos_size * tp1_pct +
                (entry - tp2) / entry * pos_size * tp2_pct
            )
    elif tp1_hit:
        if direction == "LONG":
            gross = (tp1 - entry) / entry * pos_size * tp1_pct
        else:
            gross = (entry - tp1) / entry * pos_size * tp1_pct
    else:
        if direction == "LONG":
            gross = (exit_price - entry) / entry * pos_size
        else:
            gross = (entry - exit_price) / entry * pos_size

    return round(gross - pos_size * fee_mult, 4)


def run_backtest(
    coin:     str,
    capital:  float = 1000.0,
    leverage: int   = 10,
) -> dict:
    log.info("Backtest started: %s", coin)

    df_4h  = load_candles(coin, "4h",  limit=2000)
    df_1h  = load_candles(coin, "1h",  limit=5000)
    df_15m = load_candles(coin, "15m", limit=20000)

    if df_4h is None or len(df_4h) < WINDOW_4H + 50:
        return {"error": f"Insufficient 4H data: {coin}"}
    if df_1h is None or len(df_1h) < WINDOW_1H + 50:
        return {"error": f"Insufficient 1H data: {coin}"}
    if df_15m is None or len(df_15m) < WINDOW_15M + 20:
        return {"error": f"Insufficient 15M data: {coin}"}

    split_idx    = int(len(df_4h) * 0.70)
    df_4h_train  = df_4h.iloc[:split_idx]
    df_4h_test   = df_4h.iloc[split_idx:]

    log.info(
        "Walk-forward split: train=%s candles test=%s candles",
        len(df_4h_train), len(df_4h_test),
    )

    train_result = _run_period(
        coin     = coin,
        df_4h    = df_4h_train,
        df_1h    = df_1h,
        df_15m   = df_15m,
        capital  = capital,
        leverage = leverage,
        label    = "train",
    )

    test_result = _run_period(
        coin     = coin,
        df_4h    = df_4h_test,
        df_1h    = df_1h,
        df_15m   = df_15m,
        capital  = capital,
        leverage = leverage,
        label    = "test",
    )

    if not train_result.get("trades") and not test_result.get("trades"):
        return {
            "coin":          coin,
            "error":         "No trades generated in either period",
            "total_signals": 0,
            "total_trades":  0,
        }

    from backtest.report import build_report

    all_trades   = (train_result.get("trades", []) + test_result.get("trades", []))
    all_signals  = (train_result.get("signals_log", []) + test_result.get("signals_log", []))
    final_equity = capital + sum(t["pnl"] for t in all_trades)

    report = build_report(
        coin         = coin,
        trades       = all_trades,
        signals_log  = all_signals,
        capital      = capital,
        final_equity = final_equity,
    )

    report["walk_forward"] = {
        "train": {
            "period":      f"{df_4h_train.index[0].date()} → {df_4h_train.index[-1].date()}",
            "trades":      len(train_result.get("trades", [])),
            "win_rate":    train_result.get("win_rate", 0),
            "total_pnl":   train_result.get("total_pnl", 0),
        },
        "test": {
            "period":      f"{df_4h_test.index[0].date()} → {df_4h_test.index[-1].date()}",
            "trades":      len(test_result.get("trades", [])),
            "win_rate":    test_result.get("win_rate", 0),
            "total_pnl":   test_result.get("total_pnl", 0),
        },
        "oos_degradation": round(
            (train_result.get("win_rate", 0) - test_result.get("win_rate", 0)), 1
        ),
    }

    return report


def _run_period(
    coin:     str,
    df_4h:    pd.DataFrame,
    df_1h:    pd.DataFrame,
    df_15m:   pd.DataFrame,
    capital:  float,
    leverage: int,
    label:    str,
) -> dict:
    trades           = []
    signals_log      = []
    equity           = capital
    peak_equity      = capital
    open_trades_list = []
    skipped          = 0

    for i in range(WINDOW_4H, len(df_4h) - 1):
        current_ts = df_4h.index[i]

        open_trades_list = [
            t for t in open_trades_list
            if t["close_ts"] > current_ts
        ]

        if len(open_trades_list) >= HE["max_open_trades"]:
            skipped += 1
            continue

        d4h_w  = df_4h.iloc[i - WINDOW_4H:i].copy()
        d1h_w  = _align_window(df_1h,  current_ts, WINDOW_1H)
        d15m_w = _align_window(df_15m, current_ts, WINDOW_15M)

        if len(d1h_w) < 100 or len(d15m_w) < 20:
            skipped += 1
            continue

        try:
            d4h  = calculate_all(d4h_w, timeframe="4h")
            d1h  = calculate_all(d1h_w, timeframe="1h")
            d15m = calculate_all(d15m_w, timeframe="15m")

            price = float(d4h.get("price") or 0)
            if not price or price <= 0:
                continue

            d1w_stub = None
            regime   = detect_regime(d4h, d1w_stub)

            if regime.is_volatile:
                skipped += 1
                continue

            trend = detect_trend(d4h, coin, df_1d=None, df_1w=None)

            if not trend.passed:
                continue

            direction = trend.direction
            atr_1h    = float(d1h.get("atr") or price * 0.01)
            atr_15m   = float(d15m.get("atr") or price * 0.005)

            reversion = detect_reversion(d1h, d1h_w, direction)

            if not reversion.window_open:
                continue

            ict = confirm_ict(
                df_4h   = d4h_w,
                d4h     = d4h,
                df_1h   = d1h_w,
                d1h     = d1h,
                df_15m  = d15m_w,
                d15m    = d15m,
                direction = direction,
                atr_1h  = atr_1h,
                atr_15m = atr_15m,
            )

            if not ict.confirmed:
                continue

            entry = float(ict.entry_price) if ict.entry_price else 0.0
            if not entry:
                is_long = direction == "LONG"
                zone    = ict.zone
                if zone:
                    entry = float(zone.top) if is_long else float(zone.bottom)
                else:
                    entry = price

            risk = calculate_risk(
                direction = direction,
                entry     = entry,
                sweep     = ict.sweep,
                zone      = ict.zone,
                ict       = ict.trigger,
                atr_15m   = atr_15m,
                d1h       = d1h,
                d4h       = d4h,
            )

            if not risk.valid:
                continue

            combined = ict.score

            if combined >= HE["grade_aplus"] / 100:
                grade = "A+"
            elif combined >= HE["grade_a"] / 100:
                grade = "A"
            elif combined >= HE["grade_b"] / 100:
                grade = "B"
            else:
                continue

            if grade not in ("A+", "A"):
                continue

            signals_log.append({
                "date":      str(current_ts.date()),
                "grade":     grade,
                "direction": direction,
                "price":     price,
                "entry":     entry,
                "score":     combined,
                "regime":    regime.label,
            })

            sim = _simulate_trade(
                df_4h      = df_4h,
                current_ts = current_ts,
                direction  = direction,
                entry      = entry,
                sl         = risk.sl,
                tp1        = risk.tp1,
                tp2        = risk.tp2,
            )

            open_trades_list.append({
                "open_ts":  current_ts,
                "close_ts": sim.get("close_ts", current_ts),
            })

            risk_amt = equity * HE["base_risk_pct"] * regime.size_mult
            pos_size = risk_amt / (risk.sl_pct / 100)

            pnl = _calculate_pnl(
                direction  = direction,
                entry      = entry,
                exit_price = sim["exit_price"],
                pos_size   = pos_size,
                tp1_hit    = sim["tp1_hit"],
                tp2_hit    = sim["tp2_hit"],
                tp1        = risk.tp1,
                tp2        = risk.tp2,
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
                "entry":       round(entry,          6),
                "sl":          round(risk.sl,        6),
                "tp1":         round(risk.tp1,       6),
                "tp2":         round(risk.tp2,       6) if risk.tp2 else None,
                "exit_price":  round(sim["exit_price"], 6),
                "outcome":     sim["outcome"],
                "pnl":         pnl,
                "equity":      round(equity, 4),
                "drawdown":    drawdown,
                "candles":     sim.get("candles"),
                "reason":      sim.get("reason", ""),
                "tp1_hit":     sim.get("tp1_hit", False),
                "tp2_hit":     sim.get("tp2_hit", False),
                "sweep_score": ict.sweep_score,
                "zone_score":  ict.zone_score,
                "combined":    combined,
                "regime":      regime.label,
                "period":      label,
            })

        except Exception as e:
            log.debug("Backtest candle %s error: %s", i, e)
            continue

    wins      = [t for t in trades if t["outcome"] == "win"]
    win_rate  = round(len(wins) / len(trades) * 100, 1) if trades else 0
    total_pnl = round(sum(t["pnl"] for t in trades), 4)

    log.info(
        "Period %s complete: %s trades win_rate:%s%% pnl:$%.2f skipped:%s",
        label, len(trades), win_rate, total_pnl, skipped,
    )

    return {
        "trades":      trades,
        "signals_log": signals_log,
        "win_rate":    win_rate,
        "total_pnl":   total_pnl,
        "skipped":     skipped,
    }