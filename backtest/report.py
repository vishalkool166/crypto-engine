import logging
from database import SessionLocal, BacktestResult
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def build_report(
    coin:         str,
    trades:       list,
    signals_log:  list,
    capital:      float,
    final_equity: float
) -> dict:

    if not trades:
        return {"error": "No trades to report"}

    wins     = [t for t in trades if t["outcome"] == "win"]
    losses   = [t for t in trades if t["outcome"] == "loss"]
    timeouts = [t for t in trades if t["outcome"] == "timeout"]

    total    = len(trades)
    win_rate = round(len(wins) / total * 100, 1) if total else 0

    pnls        = [t["pnl"] for t in trades]
    total_pnl   = round(sum(pnls), 4)
    best_trade  = round(max(pnls), 4)
    worst_trade = round(min(pnls), 4)
    avg_trade   = round(sum(pnls) / len(pnls), 4)

    max_dd = round(max((t["drawdown"] for t in trades), default=0), 2)

    aplus  = [t for t in trades if t["grade"] == "A+"]
    a_only = [t for t in trades if t["grade"] == "A"]

    aplus_wins = [t for t in aplus  if t["outcome"] == "win"]
    a_wins     = [t for t in a_only if t["outcome"] == "win"]

    period_start = trades[0]["date"]  if trades else "--"
    period_end   = trades[-1]["date"] if trades else "--"

    max_consec_wins   = _max_consecutive(trades, "win")
    max_consec_losses = _max_consecutive(trades, "loss")

    gross_profit  = sum(p for p in pnls if p > 0)
    gross_loss    = abs(sum(p for p in pnls if p < 0))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0

    expectancy = round(
        (win_rate / 100 * avg_trade) -
        ((1 - win_rate / 100) * abs(worst_trade)),
        4
    )

    tp1_trades  = [t for t in trades if t.get("tp1_hit")]
    tp2_trades  = [t for t in trades if t.get("tp2_hit")]
    be_trades   = [t for t in wins   if t.get("reason") == "TP1 + BE stop"]

    phase_breakdown = {
        "tp1_hit_count":  len(tp1_trades),
        "tp2_hit_count":  len(tp2_trades),
        "be_stop_count":  len(be_trades),
        "tp1_hit_rate":   round(len(tp1_trades) / total * 100, 1) if total else 0,
        "tp2_hit_rate":   round(len(tp2_trades) / total * 100, 1) if total else 0,
        "be_stop_rate":   round(len(be_trades)  / total * 100, 1) if total else 0,
    }

    regime_breakdown  = _breakdown_by_field(trades, "regime")
    session_breakdown = _breakdown_by_field(trades, "session")

    report = {
        "coin":               coin,
        "period_start":       period_start,
        "period_end":         period_end,
        "capital":            capital,
        "final_equity":       round(final_equity, 4),
        "total_return":       round((final_equity - capital) / capital * 100, 2),
        "total_signals":      len(signals_log),
        "aplus_signals":      len([s for s in signals_log if s["grade"] == "A+"]),
        "a_signals":          len([s for s in signals_log if s["grade"] == "A"]),
        "total_trades":       total,
        "wins":               len(wins),
        "losses":             len(losses),
        "timeouts":           len(timeouts),
        "win_rate":           win_rate,
        "total_pnl":          total_pnl,
        "best_trade":         best_trade,
        "worst_trade":        worst_trade,
        "avg_trade":          avg_trade,
        "max_drawdown":       max_dd,
        "profit_factor":      profit_factor,
        "expectancy":         expectancy,
        "max_consec_wins":    max_consec_wins,
        "max_consec_losses":  max_consec_losses,
        "phase_breakdown":    phase_breakdown,
        "regime_breakdown":   regime_breakdown,
        "session_breakdown":  session_breakdown,
        "by_grade": {
            "A+": {
                "trades":   len(aplus),
                "wins":     len(aplus_wins),
                "win_rate": round(len(aplus_wins) / len(aplus) * 100, 1) if aplus else 0,
                "pnl":      round(sum(t["pnl"] for t in aplus), 4)
            },
            "A": {
                "trades":   len(a_only),
                "wins":     len(a_wins),
                "win_rate": round(len(a_wins) / len(a_only) * 100, 1) if a_only else 0,
                "pnl":      round(sum(t["pnl"] for t in a_only), 4)
            }
        },
        "trades": trades
    }

    _save_to_db(report, coin)

    log.info(
        f"Backtest: {coin} WR:{win_rate}% "
        f"PnL:${total_pnl} PF:{profit_factor} Trades:{total}"
    )

    return report


def _breakdown_by_field(trades: list, field: str) -> dict:
    breakdown = {}
    for t in trades:
        val = t.get(field, "unknown") or "unknown"
        if val not in breakdown:
            breakdown[val] = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0}
        breakdown[val]["trades"] += 1
        if t["outcome"] == "win":
            breakdown[val]["wins"] += 1
        elif t["outcome"] == "loss":
            breakdown[val]["losses"] += 1
        breakdown[val]["pnl"] = round(breakdown[val]["pnl"] + t["pnl"], 4)

    for val in breakdown:
        t = breakdown[val]["trades"]
        w = breakdown[val]["wins"]
        breakdown[val]["win_rate"] = round(w / t * 100, 1) if t > 0 else 0

    return breakdown


def _max_consecutive(trades: list, outcome: str) -> int:
    max_c = 0
    cur_c = 0
    for t in trades:
        if t["outcome"] == outcome:
            cur_c += 1
            max_c = max(max_c, cur_c)
        else:
            cur_c = 0
    return max_c


def _save_to_db(report: dict, coin: str):
    db = SessionLocal()
    try:
        row = BacktestResult(
            coin          = coin,
            period_start  = report["period_start"],
            period_end    = report["period_end"],
            total_signals = report["total_signals"],
            aplus_signals = report["aplus_signals"],
            a_signals     = report["a_signals"],
            total_trades  = report["total_trades"],
            wins          = report["wins"],
            losses        = report["losses"],
            win_rate      = report["win_rate"],
            total_pnl     = report["total_pnl"],
            max_drawdown  = report["max_drawdown"],
            best_trade    = report["best_trade"],
            worst_trade   = report["worst_trade"],
            avg_trade     = report["avg_trade"],
            notes         = (
                f"PF:{report['profit_factor']} "
                f"Return:{report['total_return']}% "
                f"Expectancy:{report['expectancy']} "
                f"TP1rate:{report['phase_breakdown']['tp1_hit_rate']}% "
                f"TP2rate:{report['phase_breakdown']['tp2_hit_rate']}%"
            )
        )
        db.add(row)
        db.commit()
        log.info(f"Backtest saved: {coin}")
    except Exception as e:
        log.error(f"Backtest DB save error: {e}")
        db.rollback()
    finally:
        db.close()