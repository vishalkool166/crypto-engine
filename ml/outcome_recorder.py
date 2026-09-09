import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


async def record(trade_id: int) -> None:
    try:
        from database import get_session, Trade as TradeModel, TradeOutcome
        with get_session() as db:
            trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if not trade:
                return
            if not trade.outcome or trade.outcome == "pending":
                return

            existing = db.query(TradeOutcome).filter(
                TradeOutcome.trade_id == trade_id
            ).first()
            if existing:
                return

            pnl      = float(trade.binance_net_pnl or trade.net_pnl or trade.pnl or 0)
            sl_dist  = abs(float(trade.entry_price or 0) - float(trade.sl_price or 0))
            pnl_r    = round(pnl / sl_dist, 4) if sl_dist > 0 else 0.0

            db.add(TradeOutcome(
                trade_id          = trade_id,
                signal_id         = trade.signal_id,
                recorded_at       = datetime.now(timezone.utc),
                system_version    = trade.system_version,
                coin              = trade.coin,
                direction         = trade.direction,
                grade             = trade.grade,
                outcome           = trade.outcome,
                close_reason      = trade.close_reason,
                entry_price       = trade.entry_price,
                exit_price        = trade.exit_price,
                sl_price          = trade.sl_price,
                tp1_price         = trade.tp1_price,
                pnl               = pnl,
                pnl_r             = pnl_r,
                net_pnl           = pnl,
                total_commission  = trade.total_commission,
                funding_fees      = trade.funding_fees_paid,
                slippage_entry_pct= trade.slippage_entry_pct,
                slippage_exit_pct = trade.slippage_exit_pct,
                mae               = trade.mae,
                mfe               = trade.mfe,
                duration_hours    = trade.duration_hours,
                tp1_hit           = trade.tp1_hit,
                session           = trade.session_at_entry,
                regime            = trade.regime_at_entry,
                combined_score    = trade.score_at_entry,
                drawdown_at_entry = trade.drawdown_at_entry,
                win_rate_at_entry = trade.win_rate_at_entry,
                balance_at_open   = trade.balance_at_open,
                binance_realized_pnl    = trade.binance_realized_pnl,
                binance_commission_total= trade.binance_commission_total,
                binance_funding_total   = trade.binance_funding_total,
                binance_net_pnl         = trade.binance_net_pnl,
                binance_entry_price     = trade.binance_entry_price,
                binance_exit_price      = trade.binance_exit_price,
            ))
            log.info("Outcome recorded: trade_id=%s outcome=%s pnl=%.4f", trade_id, trade.outcome, pnl)

    except Exception as e:
        log.error("outcome_recorder.record trade_id=%s: %s", trade_id, e)