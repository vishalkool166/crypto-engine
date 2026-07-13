import logging
from datetime import datetime, timezone, timedelta, date
from database import get_session, SessionLocal
from config import cfg

log = logging.getLogger(__name__)


def get_overall_stats(min_trades: int = 1) -> dict:
    try:
        from database import Trade as TradeModel
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).order_by(TradeModel.opened_at.asc()).all()

        if len(closed) < min_trades:
            return {"error": f"Need {min_trades} trades, have {len(closed)}"}

        return _build_stats(closed)

    except Exception as e:
        log.error("get_overall_stats: %s", e)
        return {}


def get_stats_by_version() -> list:
    try:
        from database import Trade as TradeModel
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"]),
                TradeModel.system_version.isnot(None)
            ).all()

        by_version: dict = {}
        for t in closed:
            v = t.system_version
            if v not in by_version:
                by_version[v] = []
            by_version[v].append(t)

        result = []
        for version, trades in by_version.items():
            stats            = _build_stats(trades)
            stats["version"] = version
            result.append(stats)

        result.sort(key=lambda x: x["version"])
        return result

    except Exception as e:
        log.error("get_stats_by_version: %s", e)
        return []


def get_stats_by_session(min_trades: int = 5) -> dict:
    try:
        from database import Trade as TradeModel
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"]),
                TradeModel.session_at_entry.isnot(None)
            ).all()

        by_session: dict = {}
        for t in closed:
            s = t.session_at_entry or "Unknown"
            if s not in by_session:
                by_session[s] = []
            by_session[s].append(t)

        result = {}
        for session, trades in by_session.items():
            if len(trades) >= min_trades:
                result[session] = _build_stats(trades)

        return result

    except Exception as e:
        log.error("get_stats_by_session: %s", e)
        return {}


def get_stats_by_regime(min_trades: int = 5) -> dict:
    try:
        from database import Trade as TradeModel
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"]),
                TradeModel.regime_at_entry.isnot(None)
            ).all()

        by_regime: dict = {}
        for t in closed:
            r = t.regime_at_entry or "Unknown"
            if r not in by_regime:
                by_regime[r] = []
            by_regime[r].append(t)

        result = {}
        for regime, trades in by_regime.items():
            if len(trades) >= min_trades:
                result[regime] = _build_stats(trades)

        return result

    except Exception as e:
        log.error("get_stats_by_regime: %s", e)
        return {}


def get_stats_by_grade(min_trades: int = 3) -> dict:
    try:
        from database import Trade as TradeModel
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).all()

        by_grade: dict = {}
        for t in closed:
            g = t.grade or "Unknown"
            if g not in by_grade:
                by_grade[g] = []
            by_grade[g].append(t)

        result = {}
        for grade, trades in by_grade.items():
            if len(trades) >= min_trades:
                result[grade] = _build_stats(trades)

        return result

    except Exception as e:
        log.error("get_stats_by_grade: %s", e)
        return {}


def get_stats_by_direction(min_trades: int = 5) -> dict:
    try:
        from database import Trade as TradeModel
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).all()

        by_dir: dict = {}
        for t in closed:
            d = t.direction or "Unknown"
            if d not in by_dir:
                by_dir[d] = []
            by_dir[d].append(t)

        result = {}
        for direction, trades in by_dir.items():
            if len(trades) >= min_trades:
                result[direction] = _build_stats(trades)

        return result

    except Exception as e:
        log.error("get_stats_by_direction: %s", e)
        return {}


def get_stats_by_day_of_week(min_trades: int = 3) -> dict:
    try:
        from database import Trade as TradeModel
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).all()

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        by_day: dict = {}

        for t in closed:
            if not t.opened_at:
                continue
            dow = t.opened_at.weekday()
            key = day_names[dow]
            if key not in by_day:
                by_day[key] = []
            by_day[key].append(t)

        result = {}
        for day, trades in by_day.items():
            if len(trades) >= min_trades:
                result[day] = _build_stats(trades)

        return result

    except Exception as e:
        log.error("get_stats_by_day_of_week: %s", e)
        return {}


def get_stats_by_sweep_score_bucket(min_trades: int = 5) -> dict:
    try:
        from database import Signal as SignalModel, Trade as TradeModel
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"]),
                TradeModel.signal_id.isnot(None)
            ).all()

            signal_ids = [t.signal_id for t in closed]
            signals    = db.query(SignalModel).filter(
                SignalModel.id.in_(signal_ids)
            ).all()

        sig_map = {s.id: s for s in signals}

        buckets: dict = {
            "0.00-0.20": [],
            "0.20-0.30": [],
            "0.30-0.40": [],
            "0.40-0.50": [],
            "0.50-0.65": [],
            "0.65-0.80": [],
            "0.80-1.00": [],
        }

        for t in closed:
            sig = sig_map.get(t.signal_id)
            if not sig:
                continue
            score = float(sig.sweep_score or 0)
            if score < 0.20:
                buckets["0.00-0.20"].append(t)
            elif score < 0.30:
                buckets["0.20-0.30"].append(t)
            elif score < 0.40:
                buckets["0.30-0.40"].append(t)
            elif score < 0.50:
                buckets["0.40-0.50"].append(t)
            elif score < 0.65:
                buckets["0.50-0.65"].append(t)
            elif score < 0.80:
                buckets["0.65-0.80"].append(t)
            else:
                buckets["0.80-1.00"].append(t)

        result = {}
        for bucket, trades in buckets.items():
            if len(trades) >= min_trades:
                result[bucket] = _build_stats(trades)

        return result

    except Exception as e:
        log.error("get_stats_by_sweep_score_bucket: %s", e)
        return {}


def get_recent_trend(window: int = 20) -> dict:
    try:
        from database import Trade as TradeModel
        with SessionLocal() as db:
            recent = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).order_by(TradeModel.opened_at.desc()).limit(window).all()

            all_time = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).all()

        if not recent:
            return {}

        recent_stats   = _build_stats(recent)
        all_time_stats = _build_stats(all_time) if all_time else {}

        recent_wr   = recent_stats.get("win_rate", 0)
        all_time_wr = all_time_stats.get("win_rate", 0)

        trend = (
            "improving" if recent_wr > all_time_wr + 5 else
            "degrading"  if recent_wr < all_time_wr - 5 else
            "stable"
        )

        return {
            "recent_window":    window,
            "recent_win_rate":  recent_wr,
            "alltime_win_rate": all_time_wr,
            "trend":            trend,
            "recent_pnl":       recent_stats.get("total_pnl", 0),
            "recent_trades":    len(recent),
        }

    except Exception as e:
        log.error("get_recent_trend: %s", e)
        return {}


def get_expectancy_stats() -> dict:
    try:
        from database import Trade as TradeModel
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).all()

        if not closed:
            return {"error": "No closed trades"}

        wins   = [float(t.net_pnl or t.pnl or 0) for t in closed if t.outcome == "win"]
        losses = [abs(float(t.net_pnl or t.pnl or 0)) for t in closed if t.outcome == "loss"]

        total     = len(closed)
        win_rate  = len(wins)  / total
        loss_rate = len(losses) / total
        avg_win   = sum(wins)   / len(wins)   if wins   else 0.0
        avg_loss  = sum(losses) / len(losses) if losses else 0.0

        expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)

        payoff = avg_win / avg_loss if avg_loss > 0 else 0.0

        kelly = win_rate - (loss_rate / payoff) if payoff > 0 else 0.0

        return {
            "expectancy":   round(expectancy, 4),
            "win_rate":     round(win_rate  * 100, 1),
            "loss_rate":    round(loss_rate * 100, 1),
            "avg_win":      round(avg_win,  4),
            "avg_loss":     round(avg_loss, 4),
            "payoff_ratio": round(payoff,   2),
            "kelly_pct":    round(kelly * 100, 1),
            "total_trades": total,
        }

    except Exception as e:
        log.error("get_expectancy_stats: %s", e)
        return {}


def get_efficiency_stats(min_trades: int = 10) -> dict:
    try:
        from database import SessionLocal, TradeOutcome
        with SessionLocal() as db:
            outcomes = db.query(TradeOutcome).filter(
                TradeOutcome.capital_efficiency.isnot(None)
            ).all()

        if len(outcomes) < min_trades:
            return {"error": f"Need {min_trades} outcomes with efficiency data, have {len(outcomes)}"}

        cap_eff   = [float(o.capital_efficiency) for o in outcomes if o.capital_efficiency is not None]
        risk_mult = [float(o.risk_multiple)       for o in outcomes if o.risk_multiple       is not None]
        fee_pct   = [float(o.fee_pct_of_profit)   for o in outcomes if o.fee_pct_of_profit   is not None and o.fee_pct_of_profit > 0]
        captured  = [float(o.captured_move_pct)   for o in outcomes if o.captured_move_pct   is not None and o.captured_move_pct > 0]

        return {
            "avg_capital_efficiency": round(sum(cap_eff)   / len(cap_eff),   4) if cap_eff   else 0.0,
            "avg_risk_multiple":      round(sum(risk_mult) / len(risk_mult),  4) if risk_mult else 0.0,
            "avg_fee_pct_of_profit":  round(sum(fee_pct)   / len(fee_pct),    2) if fee_pct   else 0.0,
            "avg_captured_move_pct":  round(sum(captured)  / len(captured),   1) if captured  else 0.0,
            "samples":                len(outcomes),
        }

    except Exception as e:
        log.error("get_efficiency_stats: %s", e)
        return {}


def get_drawdown_history() -> dict:
    try:
        from database import Trade as TradeModel
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"]),
                TradeModel.net_pnl.isnot(None)
            ).order_by(TradeModel.opened_at.asc()).all()

        if not closed:
            return {"current_drawdown": 0.0, "max_drawdown": 0.0, "peak_equity": 0.0}

        equity       = 0.0
        peak         = 0.0
        max_dd       = 0.0
        equity_curve = []

        for t in closed:
            equity += float(t.net_pnl or t.pnl or 0)
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
            equity_curve.append({
                "date":   t.opened_at.strftime("%Y-%m-%d") if t.opened_at else "",
                "equity": round(equity, 4),
                "dd":     round(dd, 2),
            })

        current_dd = (peak - equity) / peak * 100 if peak > 0 else 0.0

        return {
            "current_drawdown": round(current_dd, 2),
            "max_drawdown":     round(max_dd,     2),
            "peak_equity":      round(peak,        4),
            "current_equity":   round(equity,      4),
            "equity_curve":     equity_curve[-100:],
        }

    except Exception as e:
        log.error("get_drawdown_history: %s", e)
        return {}


def get_win_rate_at_threshold(
    parameter:  str,
    thresholds: list,
    min_trades: int = 10,
) -> list:
    try:
        from database import Signal as SignalModel, Trade as TradeModel

        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"]),
                TradeModel.signal_id.isnot(None)
            ).all()

            signal_ids = [t.signal_id for t in closed]
            signals    = db.query(SignalModel).filter(
                SignalModel.id.in_(signal_ids)
            ).all()

        sig_map = {s.id: s for s in signals}

        param_field_map = {
            "sweep_min_score":   "sweep_score",
            "zone_min_score":    "market_score",
            "grade_a_threshold": "score",
        }

        field = param_field_map.get(parameter, "score")

        results = []
        for threshold in thresholds:
            qualifying = []
            for t in closed:
                sig = sig_map.get(t.signal_id)
                if not sig:
                    continue
                val = float(getattr(sig, field, 0) or 0)
                if field == "score":
                    val = val / 100.0 if val > 1.0 else val
                if val >= threshold:
                    qualifying.append(t)

            if len(qualifying) >= min_trades:
                wins = sum(1 for t in qualifying if t.outcome == "win")
                wr   = round(wins / len(qualifying) * 100, 1)
                results.append({
                    "threshold":    threshold,
                    "trades":       len(qualifying),
                    "wins":         wins,
                    "win_rate":     wr,
                    "win_rate_raw": wins / len(qualifying),
                })

        return results

    except Exception as e:
        log.error("get_win_rate_at_threshold %s: %s", parameter, e)
        return []


def get_full_report() -> dict:
    try:
        return {
            "overall":         get_overall_stats(),
            "by_version":      get_stats_by_version(),
            "by_session":      get_stats_by_session(),
            "by_regime":       get_stats_by_regime(),
            "by_grade":        get_stats_by_grade(),
            "by_direction":    get_stats_by_direction(),
            "by_day":          get_stats_by_day_of_week(),
            "by_sweep_bucket": get_stats_by_sweep_score_bucket(),
            "recent_trend":    get_recent_trend(),
            "drawdown":        get_drawdown_history(),
            "expectancy":      get_expectancy_stats(),
            "efficiency":      get_efficiency_stats(),
            "generated_at":    datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.error("get_full_report: %s", e)
        return {}


def _build_stats(trades: list) -> dict:
    if not trades:
        return {
            "total":         0,
            "wins":          0,
            "losses":        0,
            "win_rate":      0.0,
            "total_pnl":     0.0,
            "avg_pnl":       0.0,
            "profit_factor": 0.0,
            "max_drawdown":  0.0,
            "avg_duration":  0.0,
            "tp1_hit_rate":  0.0,
        }

    wins   = [t for t in trades if t.outcome == "win"]
    losses = [t for t in trades if t.outcome == "loss"]
    pnls   = [float(t.net_pnl or t.pnl or 0) for t in trades]
    total  = len(trades)
    wr     = round(len(wins) / total * 100, 1) if total > 0 else 0.0

    gross_p = sum(p for p in pnls if p > 0)
    gross_l = abs(sum(p for p in pnls if p < 0))
    pf      = round(gross_p / gross_l, 2) if gross_l > 0 else 0.0

    equity = 0.0
    peak   = 0.0
    max_dd = 0.0
    for t in sorted(trades, key=lambda x: x.opened_at or datetime.min):
        equity += float(t.net_pnl or t.pnl or 0)
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100 if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    durations = [
        float(t.duration_hours)
        for t in trades
        if hasattr(t, "duration_hours") and t.duration_hours
    ]
    avg_dur = round(sum(durations) / len(durations), 1) if durations else 0.0

    tp1_hits     = sum(1 for t in trades if t.tp1_hit)
    tp1_hit_rate = round(tp1_hits / total * 100, 1) if total > 0 else 0.0

    return {
        "total":         total,
        "wins":          len(wins),
        "losses":        len(losses),
        "win_rate":      wr,
        "total_pnl":     round(sum(pnls), 4),
        "avg_pnl":       round(sum(pnls) / total, 4) if total > 0 else 0.0,
        "profit_factor": pf,
        "max_drawdown":  round(max_dd, 2),
        "avg_duration":  avg_dur,
        "tp1_hit_rate":  tp1_hit_rate,
        "gross_profit":  round(gross_p, 4),
        "gross_loss":    round(gross_l, 4),
    }