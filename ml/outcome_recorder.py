import logging
from datetime import datetime, timezone, timedelta
from database import get_session, TradeOutcome
from config import cfg

log = logging.getLogger(__name__)


async def record(trade_id: int) -> bool:
    try:
        from database import SessionLocal, Trade as TradeModel, Signal as SignalModel
        from ml.version_registry import get_current_version

        with SessionLocal() as db:
            trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if not trade:
                log.error("outcome_recorder: trade %s not found", trade_id)
                return False

            existing = db.query(TradeOutcome).filter(
                TradeOutcome.trade_id == trade_id
            ).first()
            if existing:
                return True

            signal = None
            if trade.signal_id:
                signal = db.query(SignalModel).filter(
                    SignalModel.id == trade.signal_id
                ).first()

            entry      = float(trade.entry_price  or 0)
            exit_price = float(trade.exit_price   or 0)
            sl         = float(trade.sl_price     or 0)
            tp1        = float(trade.tp1_price    or 0)
            margin     = float(trade.margin_used  or 0)
            leverage   = int(trade.leverage       or 1)
            is_long    = trade.direction == "LONG"

            pnl_r = 0.0
            if entry and sl and exit_price:
                sl_dist = abs(entry - sl)
                if sl_dist > 0:
                    pnl_move = (exit_price - entry) if is_long else (entry - exit_price)
                    pnl_r    = round(pnl_move / sl_dist, 3)

            duration_hours = 0.0
            if trade.opened_at and trade.closed_at:
                opened = trade.opened_at
                closed = trade.closed_at
                if opened.tzinfo is None:
                    opened = opened.replace(tzinfo=timezone.utc)
                if closed.tzinfo is None:
                    closed = closed.replace(tzinfo=timezone.utc)
                duration_hours = round((closed - opened).total_seconds() / 3600, 2)

            signal_correct = None
            if entry and exit_price:
                if is_long:
                    signal_correct = exit_price > entry
                else:
                    signal_correct = exit_price < entry

            mae, mfe = await _calculate_mae_mfe(
                coin      = trade.coin,
                direction = trade.direction,
                entry     = entry,
                opened_at = trade.opened_at,
                closed_at = trade.closed_at,
            )

            prices_after = await _get_prices_after(
                coin      = trade.coin,
                closed_at = trade.closed_at,
            )

            max_move_pct = 0.0
            if entry and prices_after.get("1h"):
                moves = []
                for key in ["1h", "4h", "8h", "24h"]:
                    p = prices_after.get(key)
                    if p:
                        move = (p - entry) / entry * 100 if is_long else (entry - p) / entry * 100
                        moves.append(move)
                if moves:
                    max_move_pct = round(max(moves), 3)

            sweep_score   = float(signal.sweep_score  or 0) if signal else None
            zone_score    = None
            trigger_score = float(signal.disp_score   or 0) if signal else None
            combined      = float(signal.score        or 0) if signal else None

            session    = trade.session_at_entry or (signal.session if signal else None)
            regime     = trade.regime_at_entry  or (signal.regime  if signal else None)
            dow        = trade.opened_at.weekday() if trade.opened_at else None
            hod        = trade.opened_at.hour     if trade.opened_at else None

            net_pnl   = float(trade.net_pnl or trade.pnl or 0)
            gross_pnl = net_pnl + float(trade.total_commission or 0)

            capital_efficiency = round(net_pnl / margin, 4) if margin > 0 else 0.0

            risk_multiple = 0.0
            if entry and sl and margin and leverage:
                sl_dist = abs(entry - sl)
                if sl_dist > 0:
                    position_size = margin * leverage
                    risk_amt      = position_size * (sl_dist / entry)
                    risk_multiple = round(net_pnl / risk_amt, 3) if risk_amt > 0 else 0.0

            fee_pct_of_profit = 0.0
            if gross_pnl > 0:
                fee_pct_of_profit = round(
                    float(trade.total_commission or 0) / gross_pnl * 100, 2
                )

            captured_move_pct = 0.0
            move_left_pct     = 0.0
            if mfe > 0 and gross_pnl > 0 and margin > 0 and leverage > 0:
                max_possible = (mfe / 100) * margin * leverage
                if max_possible > 0:
                    captured_move_pct = round(gross_pnl / max_possible * 100, 1)
                    captured_move_pct = min(captured_move_pct, 100.0)
                    move_left_pct     = round(100.0 - captured_move_pct, 1)

            thesis_strength_at_close = trade.thesis_strength_at_close
            thesis_pillars_at_close  = trade.thesis_pillars_at_close
            thesis_exit_reason       = trade.thesis_exit_reason
            velocity_at_close        = trade.velocity_at_close

            if not thesis_strength_at_close:
                try:
                    from trade.thesis_tracker import get_thesis
                    thesis = get_thesis(trade_id)
                    if thesis:
                        thesis_strength_at_close = thesis.thesis_strength
                        thesis_pillars_at_close  = _pillars_json(thesis)
                        thesis_exit_reason       = thesis.action_reason
                        velocity_at_close        = thesis.velocity
                except Exception:
                    pass

            outcome = TradeOutcome(
                trade_id                 = trade_id,
                signal_id                = trade.signal_id,
                system_version           = trade.system_version or get_current_version(),
                coin                     = trade.coin,
                direction                = trade.direction,
                grade                    = trade.grade,
                outcome                  = trade.outcome,
                close_reason             = trade.close_reason,
                entry_price              = entry,
                exit_price               = exit_price,
                sl_price                 = sl,
                tp1_price                = tp1,
                pnl                      = float(trade.pnl or 0),
                pnl_r                    = pnl_r,
                net_pnl                  = net_pnl,
                total_commission         = float(trade.total_commission  or 0),
                funding_fees             = float(trade.funding_fees_paid or 0),
                slippage_entry_pct       = float(trade.slippage_entry_pct or 0),
                slippage_exit_pct        = float(trade.slippage_exit_pct  or 0),
                mae                      = mae,
                mfe                      = mfe,
                duration_hours           = duration_hours,
                tp1_hit                  = bool(trade.tp1_hit),
                tp2_hit                  = trade.close_reason == "tp2_hit",
                signal_direction_correct = signal_correct,
                price_1h_after           = prices_after.get("1h"),
                price_4h_after           = prices_after.get("4h"),
                price_8h_after           = prices_after.get("8h"),
                price_24h_after          = prices_after.get("24h"),
                max_move_pct             = max_move_pct,
                session                  = session,
                regime                   = regime,
                day_of_week              = dow,
                hour_of_day              = hod,
                sweep_score              = sweep_score,
                zone_score               = zone_score,
                trigger_score            = trigger_score,
                combined_score           = combined,
                ml_probability           = None,
                drawdown_at_entry        = trade.drawdown_at_entry,
                win_rate_at_entry        = trade.win_rate_at_entry,
                balance_at_open          = trade.balance_at_open,
                capital_efficiency       = capital_efficiency,
                risk_multiple            = risk_multiple,
                fee_pct_of_profit        = fee_pct_of_profit,
                captured_move_pct        = captured_move_pct if captured_move_pct > 0 else None,
                move_left_pct            = move_left_pct     if captured_move_pct > 0 else None,
                thesis_strength_at_close = thesis_strength_at_close,
                thesis_pillars_at_close  = thesis_pillars_at_close,
                thesis_exit_reason       = thesis_exit_reason,
                velocity_at_close        = velocity_at_close,
            )

            with get_session() as db2:
                db2.add(outcome)

        _update_trade_mae_mfe(trade_id, mae, mfe, duration_hours)

        log.info(
            "Outcome recorded: trade_id=%s coin=%s outcome=%s pnl_r=%.2f "
            "dur=%.1fh cap_eff=%.4f risk_mult=%.3f captured=%.1f%% thesis=%.2f",
            trade_id, trade.coin, trade.outcome, pnl_r,
            duration_hours, capital_efficiency, risk_multiple,
            captured_move_pct if captured_move_pct else 0.0,
            thesis_strength_at_close or 0.0,
        )
        return True

    except Exception as e:
        log.error("outcome_recorder.record trade_id=%s: %s", trade_id, e)
        return False


def _pillars_json(thesis) -> str:
    import json
    pillars = {}
    for name, pillar in thesis.pillars.items():
        pillars[name] = {
            "valid":  pillar.valid,
            "score":  round(pillar.score, 3),
            "reason": pillar.reason,
        }
    return json.dumps(pillars)


async def _calculate_mae_mfe(
    coin:      str,
    direction: str,
    entry:     float,
    opened_at: datetime,
    closed_at: datetime,
) -> tuple[float, float]:
    try:
        if not entry or not opened_at or not closed_at:
            return 0.0, 0.0

        from database import SessionLocal, Candle

        if opened_at.tzinfo is None:
            opened_at = opened_at.replace(tzinfo=timezone.utc)
        if closed_at.tzinfo is None:
            closed_at = closed_at.replace(tzinfo=timezone.utc)

        open_ms  = int(opened_at.timestamp() * 1000)
        close_ms = int(closed_at.timestamp() * 1000)

        with SessionLocal() as db:
            candles = db.query(Candle).filter(
                Candle.coin      == coin,
                Candle.timeframe == "15m",
                Candle.timestamp >= open_ms,
                Candle.timestamp <= close_ms,
            ).order_by(Candle.timestamp.asc()).all()

        if not candles:
            return 0.0, 0.0

        is_long = direction == "LONG"
        mae     = 0.0
        mfe     = 0.0

        for c in candles:
            if is_long:
                adverse   = (entry - float(c.low))  / entry * 100
                favorable = (float(c.high) - entry) / entry * 100
            else:
                adverse   = (float(c.high) - entry) / entry * 100
                favorable = (entry - float(c.low))  / entry * 100

            mae = max(mae, adverse)
            mfe = max(mfe, favorable)

        return round(mae, 4), round(mfe, 4)

    except Exception as e:
        log.error("_calculate_mae_mfe %s: %s", coin, e)
        return 0.0, 0.0


async def _get_prices_after(
    coin:      str,
    closed_at: datetime,
) -> dict:
    try:
        if not closed_at:
            return {}

        from database import SessionLocal, Candle

        if closed_at.tzinfo is None:
            closed_at = closed_at.replace(tzinfo=timezone.utc)

        close_ms = int(closed_at.timestamp() * 1000)
        result   = {}

        offsets = {
            "1h":  1,
            "4h":  4,
            "8h":  8,
            "24h": 24,
        }

        with SessionLocal() as db:
            for label, hours in offsets.items():
                target_ms = close_ms + int(hours * 3600 * 1000)
                candle    = db.query(Candle).filter(
                    Candle.coin      == coin,
                    Candle.timeframe == "1h",
                    Candle.timestamp >= target_ms,
                ).order_by(Candle.timestamp.asc()).first()

                if candle:
                    result[label] = float(candle.close)

        return result

    except Exception as e:
        log.error("_get_prices_after %s: %s", coin, e)
        return {}


def _update_trade_mae_mfe(
    trade_id:       int,
    mae:            float,
    mfe:            float,
    duration_hours: float,
) -> None:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if trade:
                trade.mae            = mae
                trade.mfe            = mfe
                trade.duration_hours = duration_hours
    except Exception as e:
        log.error("_update_trade_mae_mfe: %s", e)


def get_outcome(trade_id: int) -> dict | None:
    try:
        with get_session() as db:
            row = db.query(TradeOutcome).filter(
                TradeOutcome.trade_id == trade_id
            ).first()
            if not row:
                return None
            return _row_to_dict(row)
    except Exception as e:
        log.error("get_outcome: %s", e)
        return None


def get_outcomes_for_analysis(min_trades: int = 50) -> list:
    try:
        with get_session() as db:
            rows = db.query(TradeOutcome).order_by(
                TradeOutcome.recorded_at.asc()
            ).all()

        if len(rows) < min_trades:
            return []

        return [_row_to_dict(r) for r in rows]

    except Exception as e:
        log.error("get_outcomes_for_analysis: %s", e)
        return []


def _row_to_dict(row: TradeOutcome) -> dict:
    return {
        "id":                       row.id,
        "trade_id":                 row.trade_id,
        "signal_id":                row.signal_id,
        "recorded_at":              row.recorded_at.isoformat() if row.recorded_at else None,
        "system_version":           row.system_version,
        "coin":                     row.coin,
        "direction":                row.direction,
        "grade":                    row.grade,
        "outcome":                  row.outcome,
        "close_reason":             row.close_reason,
        "entry_price":              row.entry_price,
        "exit_price":               row.exit_price,
        "sl_price":                 row.sl_price,
        "tp1_price":                row.tp1_price,
        "pnl":                      row.pnl,
        "pnl_r":                    row.pnl_r,
        "net_pnl":                  row.net_pnl,
        "total_commission":         row.total_commission,
        "funding_fees":             row.funding_fees,
        "slippage_entry_pct":       row.slippage_entry_pct,
        "slippage_exit_pct":        row.slippage_exit_pct,
        "mae":                      row.mae,
        "mfe":                      row.mfe,
        "duration_hours":           row.duration_hours,
        "tp1_hit":                  row.tp1_hit,
        "tp2_hit":                  row.tp2_hit,
        "signal_direction_correct": row.signal_direction_correct,
        "price_1h_after":           row.price_1h_after,
        "price_4h_after":           row.price_4h_after,
        "price_8h_after":           row.price_8h_after,
        "price_24h_after":          row.price_24h_after,
        "max_move_pct":             row.max_move_pct,
        "session":                  row.session,
        "regime":                   row.regime,
        "day_of_week":              row.day_of_week,
        "hour_of_day":              row.hour_of_day,
        "sweep_score":              row.sweep_score,
        "zone_score":               row.zone_score,
        "trigger_score":            row.trigger_score,
        "combined_score":           row.combined_score,
        "ml_probability":           row.ml_probability,
        "drawdown_at_entry":        row.drawdown_at_entry,
        "win_rate_at_entry":        row.win_rate_at_entry,
        "balance_at_open":          row.balance_at_open,
        "capital_efficiency":       row.capital_efficiency,
        "risk_multiple":            row.risk_multiple,
        "fee_pct_of_profit":        row.fee_pct_of_profit,
        "captured_move_pct":        row.captured_move_pct,
        "move_left_pct":            row.move_left_pct,
        "thesis_strength_at_close": row.thesis_strength_at_close,
        "thesis_pillars_at_close":  row.thesis_pillars_at_close,
        "thesis_exit_reason":       row.thesis_exit_reason,
        "velocity_at_close":        row.velocity_at_close,
    }