import logging
import json
from datetime import datetime, timezone, timedelta
from engines.indian.data import get_ltp, is_market_open
from engines.indian.instruments import get_instrument
from config import cfg

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


async def track_outcomes() -> None:
    try:
        from database import SessionLocal, Signal as SignalModel

        with SessionLocal() as db:
            open_signals = db.query(SignalModel).filter(
                SignalModel.market   == "indian",
                SignalModel.outcome  == "pending",
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

        price = get_ltp(inst["token"])
        if not price:
            return

        entry     = float(signal.entry or 0)
        sl        = float(signal.sl    or 0)
        tp1       = float(signal.tp1   or 0)
        direction = signal.direction
        is_long   = direction == "LONG"

        if not entry or not sl or not tp1:
            return

        outcome    = None
        exit_price = None

        if is_long:
            if price <= sl:
                outcome    = "loss"
                exit_price = sl
            elif price >= tp1:
                outcome    = "win"
                exit_price = tp1
        else:
            if price >= sl:
                outcome    = "loss"
                exit_price = sl
            elif price <= tp1:
                outcome    = "win"
                exit_price = tp1

        if outcome:
            await _close_signal(signal.id, outcome, exit_price, "tp1_hit" if outcome == "win" else "sl_hit")
            return

        now = datetime.now(IST)
        force_close_time = now.replace(hour=15, minute=15, second=0, microsecond=0)
        if now >= force_close_time:
            await _close_signal(signal.id, "timeout", price, "time_stop")

    except Exception as e:
        log.error("_check_signal id=%s: %s", signal.id, e)


async def _close_signal(signal_id: int, outcome: str, exit_price: float, reason: str) -> None:
    try:
        from database import SessionLocal, Signal as SignalModel

        with SessionLocal() as db:
            signal = db.query(SignalModel).filter(SignalModel.id == signal_id).first()
            if not signal:
                return

            entry = float(signal.entry or 0)
            is_long = signal.direction == "LONG"

            if entry > 0 and exit_price:
                if is_long:
                    pnl_pts = round(exit_price - entry, 2)
                else:
                    pnl_pts = round(entry - exit_price, 2)
            else:
                pnl_pts = 0.0

            signal.outcome    = outcome
            signal.exit_price = exit_price
            signal.pnl        = pnl_pts
            signal.notes      = reason

        log.info(
            "Indian signal closed: id=%s %s %s outcome=%s pnl=%.2f pts",
            signal_id,
            signal.coin,
            signal.direction,
            outcome,
            pnl_pts,
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

        emoji = "✅" if outcome == "win" else "❌" if outcome == "loss" else "⏱️"
        sign  = "+" if pnl_pts >= 0 else ""

        await send(
            f"{emoji} *{instrument} {direction} Closed*\n\n"
            f"Outcome:  `{outcome.upper()}`\n"
            f"Exit:     `{exit_price:.2f}`\n"
            f"PnL:      `{sign}{pnl_pts:.2f} points`\n"
            f"Reason:   `{reason}`\n\n"
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

        pnls     = [float(s.pnl or 0) for s in signals]
        total_pts= round(sum(pnls), 2)
        avg_win  = round(sum(float(s.pnl or 0) for s in wins)   / len(wins),   2) if wins   else 0
        avg_loss = round(sum(float(s.pnl or 0) for s in losses) / len(losses), 2) if losses else 0

        gross_p  = sum(p for p in pnls if p > 0)
        gross_l  = abs(sum(p for p in pnls if p < 0))
        pf       = round(gross_p / gross_l, 2) if gross_l > 0 else 0

        by_day = {}
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for s in signals:
            if s.day_of_week is not None and s.day_of_week < 5:
                day = day_names[s.day_of_week]
                if day not in by_day:
                    by_day[day] = {"wins": 0, "losses": 0, "total": 0}
                by_day[day]["total"] += 1
                if s.outcome == "win":
                    by_day[day]["wins"] += 1
                else:
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
            "total":         total,
            "wins":          len(wins),
            "losses":        len(losses),
            "timeouts":      len(timeouts),
            "win_rate":      win_rate,
            "total_pts":     total_pts,
            "avg_win_pts":   avg_win,
            "avg_loss_pts":  avg_loss,
            "profit_factor": pf,
            "by_day":        by_day,
            "by_direction":  by_direction,
        }

    except Exception as e:
        log.error("get_performance error: %s", e)
        return {}