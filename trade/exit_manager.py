import logging

log = logging.getLogger(__name__)


async def run_exit_cycle(trade: dict) -> None:
    pass


async def initialize_thesis_for_trade(trade: dict, signal_data: dict) -> None:
    try:
        from trade.thesis_tracker import create_thesis, get_thesis

        trade_id = trade["id"]

        if get_thesis(trade_id):
            return

        create_thesis(
            trade_id    = trade_id,
            coin        = trade["coin"],
            direction   = trade["direction"],
            grade       = trade.get("grade", "A"),
            entry_price = float(trade.get("entry_price") or 0),
            sl_price    = float(trade.get("sl_price")    or 0),
            tp1_price   = float(trade.get("tp1_price")   or 0),
            tp2_price   = float(trade.get("tp2_price")   or 0) or None,
            regime      = trade.get("regime_at_entry",  ""),
            session     = trade.get("session_at_entry", ""),
            signal_data = signal_data,
        )

    except Exception as e:
        log.error("initialize_thesis_for_trade trade_id=%s: %s", trade.get("id"), e)


async def load_signal_data_for_trade(trade_id: int, signal_id: int) -> dict:
    try:
        from database import SessionLocal, Signal as SignalModel
        with SessionLocal() as db:
            sig = db.query(SignalModel).filter(SignalModel.id == signal_id).first()
            if not sig:
                return {}
            return {
                "sweep_score":   float(sig.sweep_score  or 0),
                "zone_score":    float(sig.market_score or 0) / 100 if sig.market_score else 0,
                "trigger_score": float(sig.disp_score   or 0),
                "grade":         sig.grade or "A",
                "score":         float(sig.score        or 0),
            }
    except Exception as e:
        log.error("load_signal_data_for_trade: %s", e)
        return {}