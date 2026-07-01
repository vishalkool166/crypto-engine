import logging
from datetime import datetime, timezone
from database import get_session, Trade as TradeModel, Signal as SignalModel

log = logging.getLogger(__name__)


async def sync_trade_outcomes() -> dict:
    try:
        with get_session() as db:
            open_trades = db.query(TradeModel).filter(TradeModel.is_active == True).all()
            if not open_trades:
                return {"synced": 0, "total": 0, "message": "No open trades"}

            synced = 0
            for trade in open_trades:
                if not trade.signal_id:
                    continue
                sig = db.query(SignalModel).filter(SignalModel.id == trade.signal_id).first()
                if sig and sig.outcome == "pending":
                    sig.entry  = trade.entry_price
                    sig.sl     = trade.sl_price
                    sig.tp1    = trade.tp1_price
                    synced    += 1
            db.commit()

        return {"synced": synced, "total": len(open_trades), "message": f"Synced {synced} trades"}

    except Exception as e:
        log.error("sync_trade_outcomes error: %s", e)
        return {"synced": 0, "unmatched": 0, "error": str(e)}


async def get_sync_status() -> dict:
    try:
        with get_session() as db:
            total       = db.query(SignalModel).count()
            pending     = db.query(SignalModel).filter(SignalModel.outcome == "pending").count()
            closed      = db.query(SignalModel).filter(SignalModel.outcome.in_(["win", "loss"])).count()
            wins        = db.query(SignalModel).filter(SignalModel.outcome == "win").count()
            open_trades = db.query(TradeModel).filter(TradeModel.is_active == True).count()

        return {
            "total_signals":   total,
            "pending_signals": pending,
            "closed_signals":  closed,
            "open_trades":     open_trades,
            "wins":            wins,
            "losses":          closed - wins,
            "win_rate":        round(wins / closed * 100, 1) if closed > 0 else 0,
            "sync_needed":     False,
        }
    except Exception as e:
        log.error("get_sync_status error: %s", e)
        return {}