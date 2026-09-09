import logging
from datetime import datetime, timezone, timedelta
from database import SessionLocal, Trade as TradeModel

log = logging.getLogger(__name__)


def get_overall_stats(min_trades: int = 10) -> dict:
    try:
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).order_by(TradeModel.opened_at.asc()).all()

        if len(closed) < min_trades:
            return {"error": f"Need at least {min_trades} closed trades — have {len(closed)}"}

        wins     = [t for t in closed if t.outcome == "win"]
        losses   = [t for t in closed if t.outcome == "loss"]
        pnls     = [float(t.binance_net_pnl or t.net_pnl or t.pnl or 0) for t in closed]
        total    = len(closed)
        win_rate = round(len(wins) / total * 100, 1)
        total_pnl= round(sum(pnls), 4)

        gross_p  = sum(p for p in pnls if p > 0)
        gross_l  = abs(sum(p for p in pnls if p < 0))
        pf       = round(gross_p / gross_l, 2) if gross_l > 0 else 0

        peak   = 0.0
        equity = 0.0
        max_dd = 0.0
        for p in pnls:
            equity += p
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        return {
            "total":          total,
            "wins":           len(wins),
            "losses":         len(losses),
            "win_rate":       win_rate,
            "total_pnl":      total_pnl,
            "profit_factor":  pf,
            "max_drawdown":   round(max_dd, 2),
        }

    except Exception as e:
        log.error("get_overall_stats: %s", e)
        return {"error": str(e)}


def get_stats_by_session(min_trades: int = 3) -> dict:
    try:
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).all()

        by_session = {}
        for t in closed:
            s = t.session_at_entry or "Unknown"
            if s not in by_session:
                by_session[s] = []
            by_session[s].append(t)

        result = {}
        for session, trades in by_session.items():
            if len(trades) < min_trades:
                continue
            wins     = sum(1 for t in trades if t.outcome == "win")
            total    = len(trades)
            pnl      = round(sum(float(t.binance_net_pnl or t.net_pnl or t.pnl or 0) for t in trades), 4)
            result[session] = {
                "total":    total,
                "wins":     wins,
                "win_rate": round(wins / total * 100, 1),
                "pnl":      pnl,
            }

        return result

    except Exception as e:
        log.error("get_stats_by_session: %s", e)
        return {}


def get_recent_trend(window: int = 20) -> dict:
    try:
        with SessionLocal() as db:
            recent = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).order_by(TradeModel.opened_at.desc()).limit(window).all()

        if not recent:
            return {"trend": "unknown", "recent_win_rate": 0}

        wins     = sum(1 for t in recent if t.outcome == "win")
        win_rate = round(wins / len(recent) * 100, 1)

        older_window = window * 2
        with SessionLocal() as db:
            older = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).order_by(TradeModel.opened_at.desc()).limit(older_window).all()

        older_only = older[window:]
        if older_only:
            older_wins = sum(1 for t in older_only if t.outcome == "win")
            older_wr   = older_wins / len(older_only) * 100
            if win_rate > older_wr + 5:
                trend = "improving"
            elif win_rate < older_wr - 5:
                trend = "degrading"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        return {
            "trend":            trend,
            "recent_win_rate":  win_rate,
            "recent_trades":    len(recent),
        }

    except Exception as e:
        log.error("get_recent_trend: %s", e)
        return {"trend": "unknown", "recent_win_rate": 0}