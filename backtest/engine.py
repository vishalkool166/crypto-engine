import pandas as pd
import logging
from data.store import load_candles
from engines.core.indicators import get_indicators
from engines.regime.detector import detect as detect_regime
from engines.trend.direction import detect as detect_trend
from engines.core.risk import calculate_risk
from config import cfg, TAKER_FEE

log = logging.getLogger(__name__)


def _simulate_trade(
    df:        pd.DataFrame,
    current_i: int,
    direction: str,
    entry:     float,
    sl:        float,
    tp1:       float,
    tp2:       float,
) -> dict:
    future  = df.iloc[current_i:current_i + 40]
    is_long = direction == "LONG"
    tp1_hit = False

    if len(future) < 2:
        return {
            "outcome":    "timeout",
            "exit_price": entry,
            "candles":    0,
            "tp1_hit":    False,
            "tp2_hit":    False,
        }

    for j, (ts, c) in enumerate(future.iterrows()):
        h = float(c["high"])
        l = float(c["low"])

        sl_hit  = (l <= sl)  if is_long else (h >= sl)
        tp1_now = (h >= tp1) if is_long else (l <= tp1)
        tp2_now = (h >= tp2) if is_long else (l <= tp2)

        if not tp1_hit:
            if sl_hit and tp1_now:
                return {"outcome": "loss", "exit_price": sl, "candles": j+1, "tp1_hit": False, "tp2_hit": False}
            if sl_hit:
                return {"outcome": "loss", "exit_price": sl, "candles": j+1, "tp1_hit": False, "tp2_hit": False}
            if tp1_now:
                tp1_hit = True
                sl      = entry
                if not tp2:
                    return {"outcome": "win", "exit_price": tp1, "candles": j+1, "tp1_hit": True, "tp2_hit": False}
                continue
        else:
            if tp2_now:
                return {"outcome": "win", "exit_price": tp2, "candles": j+1, "tp1_hit": True, "tp2_hit": True}
            if (l <= sl) if is_long else (h >= sl):
                return {"outcome": "win", "exit_price": entry, "candles": j+1, "tp1_hit": True, "tp2_hit": False}

    last_close = float(future.iloc[-1]["close"])
    return {
        "outcome":    "win" if tp1_hit else "timeout",
        "exit_price": last_close,
        "candles":    len(future),
        "tp1_hit":    tp1_hit,
        "tp2_hit":    False,
    }


def run_backtest(
    coin:     str,
    capital:  float = 1000.0,
    leverage: int   = 10,
) -> dict:
    log.info("Backtest started: %s", coin)

    df_4h = load_candles(coin, "4h", limit=2000)
    df_1h = load_candles(coin, "1h", limit=5000)

    if df_4h is None or len(df_4h) < 250:
        return {"error": f"Insufficient 4H data: {coin}"}
    if df_1h is None or len(df_1h) < 50:
        return {"error": f"Insufficient 1H data: {coin}"}

    HE     = cfg.HYBRID_ENGINE
    trades = []
    equity = capital

    for i in range(220, len(df_4h) - 40):
        window_4h = df_4h.iloc[i-220:i]
        window_1h = df_1h[df_1h.index < df_4h.index[i]].tail(300)

        if len(window_1h) < 50:
            continue

        try:
            d4h = get_indicators(window_4h, timeframe="4h")
            d1h = get_indicators(window_1h, timeframe="1h")
        except Exception:
            continue

        regime = detect_regime(d4h)
        if regime.is_volatile:
            continue

        trend = detect_trend(d4h, coin)
        if not trend.passed:
            continue

        price     = d4h["price"]
        ema50     = d4h["ema50"]
        adx       = d4h["adx"]
        atr       = d4h["atr"]
        vol_ratio = d4h["vol_ratio"]
        direction = trend.direction

        near_ema50 = abs(price - ema50) <= atr * HE.get("ema50_atr_mult", 3.0)
        if not near_ema50:
            continue

        last      = window_4h.iloc[-1]
        o         = float(last["open"])
        c         = float(last["close"])
        h         = float(last["high"])
        l         = float(last["low"])
        rng       = h - l
        body_ratio= abs(c-o)/rng if rng > 0 else 0
        bull      = c > o

        if body_ratio < HE.get("body_ratio_min", 0.5):
            continue
        if direction == "LONG"  and not bull: continue
        if direction == "SHORT" and bull:     continue
        if vol_ratio < HE.get("volume_ratio_min", 0.8):
            continue

        swing_level = d4h["swing_low"] if direction == "LONG" else d4h["swing_high"]

        risk = calculate_risk(
            direction   = direction,
            entry       = price,
            swing_level = swing_level,
            atr         = atr,
        )

        if not risk.valid:
            continue

        from engines.scoring.scorer import score as calc_score
        rsi       = d1h["rsi"]
        score_res = calc_score(adx, rsi, vol_ratio, direction, regime.label)

        if score_res.grade == "F":
            continue

        risk_amt      = equity * HE.get("base_risk_pct", 0.01) * regime.size_mult
        pos_size      = risk_amt / (risk.sl_pct / 100)
        fee_mult      = TAKER_FEE * 2

        sim = _simulate_trade(
            df        = df_4h,
            current_i = i,
            direction = direction,
            entry     = risk.entry,
            sl        = risk.sl,
            tp1       = risk.tp1,
            tp2       = risk.tp2,
        )

        if sim["outcome"] == "timeout":
            continue

        if sim["outcome"] == "win":
            pnl = round(pos_size * (risk.sl_pct / 100) * risk.rr1 - pos_size * fee_mult, 4)
        else:
            pnl = round(-(pos_size * (risk.sl_pct / 100)) - pos_size * fee_mult, 4)

        equity += pnl

        trades.append({
            "date":      str(df_4h.index[i].date()),
            "coin":      coin,
            "grade":     score_res.grade,
            "direction": direction,
            "entry":     round(risk.entry, 6),
            "sl":        round(risk.sl,    6),
            "tp1":       round(risk.tp1,   6),
            "exit":      round(sim["exit_price"], 6),
            "outcome":   sim["outcome"],
            "pnl":       pnl,
            "equity":    round(equity, 4),
            "tp1_hit":   sim["tp1_hit"],
            "regime":    regime.label,
        })

    if not trades:
        return {
            "coin":         coin,
            "error":        "No trades generated",
            "total_signals":0,
            "total_trades": 0,
        }

    wins     = [t for t in trades if t["outcome"] == "win"]
    losses   = [t for t in trades if t["outcome"] == "loss"]
    total    = len(trades)
    win_rate = round(len(wins) / total * 100, 1) if total > 0 else 0
    pnls     = [t["pnl"] for t in trades]
    total_pnl= round(sum(pnls), 4)

    gross_p  = sum(p for p in pnls if p > 0)
    gross_l  = abs(sum(p for p in pnls if p < 0))
    pf       = round(gross_p / gross_l, 2) if gross_l > 0 else 0

    peak   = capital
    max_dd = 0.0
    eq     = capital
    for t in trades:
        eq += t["pnl"]
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    by_grade = {}
    for g in ("A+", "A", "B"):
        gt = [t for t in trades if t["grade"] == g]
        gw = [t for t in gt    if t["outcome"] == "win"]
        by_grade[g] = {
            "trades":   len(gt),
            "wins":     len(gw),
            "win_rate": round(len(gw)/len(gt)*100, 1) if gt else 0,
            "pnl":      round(sum(t["pnl"] for t in gt), 4),
        }

    period_start = trades[0]["date"]  if trades else "--"
    period_end   = trades[-1]["date"] if trades else "--"

    from backtest.report import _save_to_db
    report = {
        "coin":          coin,
        "period_start":  period_start,
        "period_end":    period_end,
        "capital":       capital,
        "final_equity":  round(equity, 4),
        "total_return":  round((equity - capital) / capital * 100, 2),
        "total_signals": total,
        "aplus_signals": by_grade.get("A+", {}).get("trades", 0),
        "a_signals":     by_grade.get("A",  {}).get("trades", 0),
        "total_trades":  total,
        "wins":          len(wins),
        "losses":        len(losses),
        "win_rate":      win_rate,
        "total_pnl":     total_pnl,
        "best_trade":    round(max(pnls), 4),
        "worst_trade":   round(min(pnls), 4),
        "avg_trade":     round(sum(pnls)/total, 4) if total > 0 else 0,
        "max_drawdown":  round(max_dd, 2),
        "profit_factor": pf,
        "by_grade":      by_grade,
        "trades":        trades,
        "walk_forward":  {},
    }

    _save_to_db(report, coin)
    log.info("Backtest complete: %s WR:%s%% PnL:$%s Trades:%s", coin, win_rate, total_pnl, total)
    return report