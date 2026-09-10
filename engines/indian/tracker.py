import logging
import json
from datetime import datetime, timezone, timedelta
from engines.indian.data import get_ltp_live, is_market_open
from engines.indian.instruments import get_instrument
from config import cfg

log = logging.getLogger(__name__)

IST              = timezone(timedelta(hours=5, minutes=30))
RUPEES_PER_POINT = 30
TIME_EXIT_HOUR   = 14
TIME_EXIT_MINUTE = 30


def _save_journey_snapshot(signal_id: int, coin: str, direction: str, price: float, entry_price: float, sl_price: float, tp_price: float, is_entry: bool = False, is_exit: bool = False) -> None:
    try:
        from database import get_session, TradeJourney
        is_long = direction == "LONG"
        pnl_pts = round(price - entry_price, 2) if is_long else round(entry_price - price, 2)
        pnl_pct = round(pnl_pts / entry_price * 100, 4) if entry_price > 0 else 0.0
        with get_session() as db:
            db.add(TradeJourney(
                trade_id    = signal_id,
                market      = "indian",
                coin        = coin,
                direction   = direction,
                price       = price,
                pnl_pts     = pnl_pts,
                pnl_pct     = pnl_pct,
                is_entry    = is_entry,
                is_exit     = is_exit,
                entry_price = entry_price,
                sl_price    = sl_price,
                tp_price    = tp_price,
            ))
    except Exception as e:
        log.error("_save_journey_snapshot: %s", e)


def _is_time_exit() -> bool:
    now = datetime.now(IST)
    return now.hour > TIME_EXIT_HOUR or (now.hour == TIME_EXIT_HOUR and now.minute >= TIME_EXIT_MINUTE)


async def track_outcomes() -> None:
    try:
        from database import SessionLocal, Signal as SignalModel

        with SessionLocal() as db:
            open_signals = db.query(SignalModel).filter(
                SignalModel.market  == "indian",
                SignalModel.outcome == "pending",
            ).all()

        if not open_signals:
            return

        log.debug("Tracking %s open Indian signals", len(open_signals))

        for signal in open_signals:
            await _check_signal(signal)

    except Exception as e:
        log.error("track_outcomes error: %s", e)


async def _check_signal(signal) -> None:
    try:
        inst = get_instrument(signal.instrument or signal.coin)
        if not inst:
            return

        from engines.indian.data import get_ltp_from_redis
        price = get_ltp_from_redis(inst["token"])
        if not price:
            ltp_data = get_ltp_live(inst["token"])
            price    = ltp_data["ltp"] if ltp_data else None
        if not price:
            return

        entry     = float(signal.entry or 0)
        sl        = float(signal.sl    or 0)
        tp1       = float(signal.tp1   or 0)
        direction = signal.direction
        is_long   = direction == "LONG"

        if not entry or not sl or not tp1:
            return

        _save_journey_snapshot(
            signal_id   = signal.id,
            coin        = signal.instrument or signal.coin,
            direction   = direction,
            price       = price,
            entry_price = entry,
            sl_price    = sl,
            tp_price    = tp1,
        )

        outcome    = None
        exit_price = None
        reason     = None

        if is_long:
            if price <= sl:
                outcome    = "loss"
                exit_price = sl
                reason     = "sl_hit"
            elif price >= tp1:
                outcome    = "win"
                exit_price = tp1
                reason     = "tp1_hit"
        else:
            if price >= sl:
                outcome    = "loss"
                exit_price = sl
                reason     = "sl_hit"
            elif price <= tp1:
                outcome    = "win"
                exit_price = tp1
                reason     = "tp1_hit"

        if not outcome and _is_time_exit():
            outcome    = "timeout"
            exit_price = price
            reason     = "time_exit_2:30pm"
            log.info(
                "Time exit triggered: signal_id=%s %s price=%.2f",
                signal.id, signal.instrument or signal.coin, price
            )

        if outcome:
            _save_journey_snapshot(
                signal_id   = signal.id,
                coin        = signal.instrument or signal.coin,
                direction   = direction,
                price       = exit_price,
                entry_price = entry,
                sl_price    = sl,
                tp_price    = tp1,
                is_exit     = True,
            )
            await _close_signal(signal.id, outcome, exit_price, reason)

    except Exception as e:
        log.error("_check_signal id=%s: %s", signal.id, e)


async def _close_signal(signal_id: int, outcome: str, exit_price: float, reason: str) -> None:
    try:
        from database import SessionLocal, Signal as SignalModel

        with SessionLocal() as db:
            signal = db.query(SignalModel).filter(SignalModel.id == signal_id).first()
            if not signal:
                return

            entry   = float(signal.entry or 0)
            is_long = signal.direction == "LONG"

            if entry > 0 and exit_price:
                pnl_pts = round(exit_price - entry, 2) if is_long else round(entry - exit_price, 2)
            else:
                pnl_pts = 0.0

            signal.outcome    = outcome
            signal.exit_price = exit_price
            signal.pnl        = pnl_pts
            signal.notes      = reason

        log.info(
            "Indian signal closed: id=%s %s %s outcome=%s pnl=%.2f pts reason=%s",
            signal_id,
            signal.coin,
            signal.direction,
            outcome,
            pnl_pts,
            reason,
        )

        await _send_outcome_alert(signal_id, signal.coin, signal.direction, outcome, exit_price, pnl_pts, reason)

    except Exception as e:
        log.error("_close_signal id=%s: %s", signal_id, e)


async def _send_outcome_alert(
    signal_id:  int,
    instrument: str,
    direction:  str,
    outcome:    str,
    exit_price: float,
    pnl_pts:    float,
    reason:     str,
) -> None:
    try:
        from alerts.telegram import send

        rupees   = round(pnl_pts * RUPEES_PER_POINT)
        emoji    = "✅" if outcome == "win" else "❌" if outcome == "loss" else "⏱️"
        pnl_emoji= "💚" if pnl_pts >= 0 else "🔴"
        sign     = "+" if pnl_pts >= 0 else ""
        r_sign   = "+" if rupees >= 0 else ""

        await send(
            f"{emoji} *{instrument} {direction} Closed*\n\n"
            f"📊 Outcome:  `{outcome.upper()}`\n"
            f"💲 Exit:     `{exit_price:.2f}`\n"
            f"{pnl_emoji} Points:   `{sign}{pnl_pts:.0f} pts`\n"
            f"💰 Rupees:   `{r_sign}₹{abs(rupees):,}` / lot\n"
            f"📝 Reason:   `{reason}`\n\n"
            f"_Signal #{signal_id} — Paper tracking_"
        )
    except Exception as e:
        log.error("_send_outcome_alert: %s", e)


def get_performance() -> dict:
    try:
        from database import SessionLocal, Signal as SignalModel

        with SessionLocal() as db:
            signals = db.query(SignalModel).filter(
                SignalModel.market == "indian",
                SignalModel.outcome.in_(["win", "loss", "timeout"]),
            ).all()

        if not signals:
            return {"total": 0, "message": "No closed signals yet"}

        wins     = [s for s in signals if s.outcome == "win"]
        losses   = [s for s in signals if s.outcome == "loss"]
        timeouts = [s for s in signals if s.outcome == "timeout"]
        total    = len(signals)
        win_rate = round(len(wins) / total * 100, 1) if total > 0 else 0

        pnls      = [float(s.pnl or 0) for s in signals]
        total_pts = round(sum(pnls), 2)
        positive  = sum(1 for p in pnls if p > 0)
        avg_win   = round(sum(float(s.pnl or 0) for s in wins)   / len(wins),   2) if wins   else 0
        avg_loss  = round(sum(float(s.pnl or 0) for s in losses) / len(losses), 2) if losses else 0

        gross_p = sum(p for p in pnls if p > 0)
        gross_l = abs(sum(p for p in pnls if p < 0))
        pf      = round(gross_p / gross_l, 2) if gross_l > 0 else 0

        by_day = {}
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for s in signals:
            if s.day_of_week is not None and s.day_of_week < 5:
                day = day_names[s.day_of_week]
                if day not in by_day:
                    by_day[day] = {"wins": 0, "losses": 0, "total": 0, "pnl_pts": 0.0}
                by_day[day]["total"]   += 1
                by_day[day]["pnl_pts"] += float(s.pnl or 0)
                if s.outcome == "win":
                    by_day[day]["wins"] += 1
                elif s.outcome == "loss":
                    by_day[day]["losses"] += 1
        for day in by_day:
            t = by_day[day]["total"]
            w = by_day[day]["wins"]
            by_day[day]["win_rate"] = round(w / t * 100, 1) if t > 0 else 0

        by_direction = {}
        for d in ["LONG", "SHORT"]:
            dt = [s for s in signals if s.direction == d]
            dw = [s for s in dt if s.outcome == "win"]
            by_direction[d] = {
                "total":    len(dt),
                "wins":     len(dw),
                "win_rate": round(len(dw) / len(dt) * 100, 1) if dt else 0,
                "pnl_pts":  round(sum(float(s.pnl or 0) for s in dt), 2),
            }

        return {
            "total":          total,
            "wins":           len(wins),
            "losses":         len(losses),
            "timeouts":       len(timeouts),
            "win_rate":       win_rate,
            "profitable_rate":round(positive / total * 100, 1) if total > 0 else 0,
            "total_pts":      total_pts,
            "avg_win_pts":    avg_win,
            "avg_loss_pts":   avg_loss,
            "profit_factor":  pf,
            "by_day":         by_day,
            "by_direction":   by_direction,
        }

    except Exception as e:
        log.error("get_performance error: %s", e)
        return {}


def get_open_signals_with_pnl() -> list:
    try:
        from database import SessionLocal, Signal as SignalModel
        from engines.indian.data import get_ltp_from_redis
        from engines.indian.instruments import get_instrument
        from datetime import date, timezone, datetime as dt

        with SessionLocal() as db:
            signals = db.query(SignalModel).filter(
                SignalModel.market  == "indian",
                SignalModel.outcome == "pending",
            ).all()

        result = []
        for s in signals:
            inst  = get_instrument(s.instrument or s.coin)
            price = get_ltp_from_redis(inst["token"]) if inst else None

            entry   = float(s.entry or 0)
            sl      = float(s.sl    or 0)
            tp1     = float(s.tp1   or 0)
            is_long = s.direction == "LONG"

            live_pnl_pts = None
            progress_pct = None

            if price and entry:
                live_pnl_pts = round(price - entry, 2) if is_long else round(entry - price, 2)
                tp_dist      = abs(tp1   - entry)
                cur_dist     = abs(price - entry)
                if tp_dist > 0:
                    progress_pct = round(min(100, cur_dist / tp_dist * 100), 1)

            opened_at = s.timestamp
            duration  = None
            if opened_at:
                if opened_at.tzinfo is None:
                    opened_at = opened_at.replace(tzinfo=timezone.utc)
                diff     = datetime.now(timezone.utc) - opened_at
                mins     = int(diff.total_seconds() / 60)
                hrs      = mins // 60
                duration = f"{hrs}h {mins % 60}m" if hrs > 0 else f"{mins}m"

            time_exit_soon = _is_time_exit()

            result.append({
                "id":             s.id,
                "instrument":     s.instrument or s.coin,
                "direction":      s.direction,
                "entry":          entry,
                "sl":             sl,
                "tp1":            tp1,
                "current_price":  price,
                "live_pnl_pts":   live_pnl_pts,
                "live_rupees":    round(live_pnl_pts * RUPEES_PER_POINT, 0) if live_pnl_pts is not None else None,
                "progress_pct":   progress_pct,
                "orb_high":       float(s.orb_high or 0),
                "orb_low":        float(s.orb_low  or 0),
                "orb_size":       float(s.orb_size  or 0),
                "duration":       duration,
                "timestamp":      s.timestamp.isoformat() if s.timestamp else None,
                "outcome":        s.outcome,
                "time_exit_soon": time_exit_soon,
            })

        return result

    except Exception as e:
        log.error("get_open_signals_with_pnl: %s", e)
        return []


def get_signal_journey(signal_id: int) -> list:
    try:
        from database import SessionLocal, TradeJourney

        with SessionLocal() as db:
            snapshots = db.query(TradeJourney).filter(
                TradeJourney.trade_id == signal_id,
                TradeJourney.market   == "indian",
            ).order_by(TradeJourney.timestamp.asc()).all()

        return [{
            "timestamp":  s.timestamp.isoformat() if s.timestamp else None,
            "price":      s.price,
            "pnl_pts":    s.pnl_pts,
            "pnl_pct":    s.pnl_pct,
            "is_entry":   s.is_entry,
            "is_exit":    s.is_exit,
            "entry_price":s.entry_price,
            "sl_price":   s.sl_price,
            "tp_price":   s.tp_price,
        } for s in snapshots]

    except Exception as e:
        log.error("get_signal_journey: %s", e)
        return []