import logging
from datetime import date, datetime, timezone
from config import cfg

log = logging.getLogger(__name__)

SE = cfg.SCALP_ENGINE

MIN_STAKE          = 5.0
MAX_RISK_PCT       = 0.02
MIN_RISK_PCT       = 0.005
PAPER_LEVERAGE_CAP = 10
LIVE_LEVERAGE_CAP  = 15
PAPER_BASE_RISK    = 0.015
LIVE_BASE_RISK     = 0.01
ML_MIN_TRADES      = 100
DAILY_LOSS_LIMIT   = 0.02

SESSION_SIZE_MULT = {
    "London/NY Overlap": 1.0,
    "London":            1.0,
    "New York":          1.0,
    "Asia":              0.5,
    "Off Hours":         0.0,
}


def _get_recent_performance() -> dict:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).order_by(TradeModel.opened_at.desc()).limit(20).all()

        if not closed:
            return {
                "total":         0,
                "win_rate":      None,
                "streak":        0,
                "streak_type":   None,
                "consec_losses": 0,
            }

        wins        = sum(1 for t in closed if t.outcome == "win")
        win_rate    = wins / len(closed)
        streak      = 0
        streak_type = None

        for t in closed:
            if streak == 0:
                streak_type = t.outcome
                streak      = 1
            elif t.outcome == streak_type:
                streak += 1
            else:
                break

        consec_losses = streak if streak_type == "loss" else 0

        return {
            "total":         len(closed),
            "win_rate":      win_rate,
            "streak":        streak,
            "streak_type":   streak_type,
            "consec_losses": consec_losses,
        }

    except Exception as e:
        log.error("_get_recent_performance: %s", e)
        return {
            "total":         0,
            "win_rate":      None,
            "streak":        0,
            "streak_type":   None,
            "consec_losses": 0,
        }


def _get_drawdown(balance: float) -> float:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"]),
                TradeModel.net_pnl.isnot(None)
            ).order_by(TradeModel.opened_at.asc()).all()

        if not closed:
            return 0.0

        total_pnl = sum(float(t.net_pnl or t.pnl or 0) for t in closed)
        starting  = balance - total_pnl
        equity    = starting
        peak      = starting

        for t in closed:
            equity += float(t.net_pnl or t.pnl or 0)
            if equity > peak:
                peak = equity

        return max(0.0, (peak - balance) / peak) if peak > 0 else 0.0

    except Exception as e:
        log.error("_get_drawdown: %s", e)
        return 0.0


def _get_today_pnl() -> float:
    try:
        from database import SessionLocal, Trade as TradeModel
        today_start = datetime(
            date.today().year,
            date.today().month,
            date.today().day,
            tzinfo=timezone.utc
        )
        with SessionLocal() as db:
            trades = db.query(TradeModel).filter(
                TradeModel.closed_at >= today_start,
                TradeModel.outcome.in_(["win", "loss"])
            ).all()
        return sum(float(t.net_pnl or t.pnl or 0) for t in trades)
    except Exception as e:
        log.error("_get_today_pnl: %s", e)
        return 0.0


def _get_open_trade_counts() -> dict:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            trades = db.query(TradeModel).filter(
                TradeModel.is_active == True
            ).all()
        return {
            "total": len(trades),
            "long":  sum(1 for t in trades if t.direction == "LONG"),
            "short": sum(1 for t in trades if t.direction == "SHORT"),
        }
    except Exception as e:
        log.error("_get_open_trade_counts: %s", e)
        return {"total": 0, "long": 0, "short": 0}


def _get_total_closed_trades() -> int:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            return db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).count()
    except Exception:
        return 0


def _leverage_from_sl(sl_pct: float, is_paper: bool) -> int:
    cap = PAPER_LEVERAGE_CAP if is_paper else LIVE_LEVERAGE_CAP
    if sl_pct < 0.5:
        lev = 15
    elif sl_pct < 1.0:
        lev = 12
    elif sl_pct < 1.5:
        lev = 10
    elif sl_pct < 2.0:
        lev = 7
    else:
        lev = 5
    return min(lev, cap)


def _grade_mult(grade: str) -> float:
    return {
        "A+": SE["grade_aplus_size_mult"],
        "A":  SE["grade_a_size_mult"],
        "B":  SE["grade_b_size_mult"],
    }.get(grade, SE["grade_b_size_mult"])


def _ml_mult(total_trades: int, ml_probability: float | None) -> float:
    if total_trades < ML_MIN_TRADES:
        return 1.0
    if ml_probability is None:
        return 1.0
    if ml_probability >= 0.75:
        return 1.10
    if ml_probability >= 0.65:
        return 1.00
    if ml_probability >= 0.55:
        return 0.85
    return 0.70


def _alignment_mult(alignment: dict | None) -> float:
    if not alignment:
        return 1.0
    return alignment.get("size_mult", 1.0)


def _session_mult(session: str) -> float:
    return SESSION_SIZE_MULT.get(session, 1.0)


def _dynamic_risk(
    base:     float,
    perf:     dict,
    drawdown: float,
) -> float:
    win_rate    = perf.get("win_rate")
    streak      = perf.get("streak", 0)
    streak_type = perf.get("streak_type")
    total       = perf.get("total", 0)

    if win_rate is None or total < 10:
        wr_mult = 0.8
    elif win_rate > 0.60:
        wr_mult = 1.20
    elif win_rate > 0.50:
        wr_mult = 1.00
    elif win_rate > 0.40:
        wr_mult = 0.85
    elif win_rate > 0.30:
        wr_mult = 0.70
    else:
        wr_mult = 0.50

    if streak_type == "win":
        if streak >= 5:
            streak_mult = 1.15
        elif streak >= 3:
            streak_mult = 1.08
        else:
            streak_mult = 1.0
    elif streak_type == "loss":
        if streak >= 2:
            streak_mult = 0.80
        else:
            streak_mult = 0.90
    else:
        streak_mult = 1.0

    if drawdown > 0.20:
        dd_mult = 0.40
    elif drawdown > 0.15:
        dd_mult = 0.60
    elif drawdown > 0.10:
        dd_mult = 0.75
    elif drawdown > 0.05:
        dd_mult = 0.90
    else:
        dd_mult = 1.00

    risk = base * wr_mult * streak_mult * dd_mult
    return max(MIN_RISK_PCT, min(MAX_RISK_PCT, risk))


def calculate(
    balance:        float,
    sl_pct:         float,
    sl_dist:        float,
    grade:          str,
    direction:      str,
    ml_probability: float | None = None,
    alignment:      dict | None  = None,
    session:        str          = "",
) -> dict:
    is_paper = cfg.PAPER_TRADING

    today_pnl   = _get_today_pnl()
    daily_limit = balance * DAILY_LOSS_LIMIT

    if today_pnl < -daily_limit:
        return {
            "skip":   True,
            "reason": (
                f"Daily loss limit hit: ${abs(today_pnl):.2f} "
                f"of ${daily_limit:.2f} — no more trades today"
            )
        }

    open_counts = _get_open_trade_counts()

    if open_counts["total"] >= SE["max_open_trades"]:
        return {"skip": True, "reason": "max_open_trades"}

    same_dir = open_counts["long"] if direction == "LONG" else open_counts["short"]
    if same_dir >= SE["max_same_direction"]:
        return {"skip": True, "reason": "max_same_direction"}

    if not balance or balance < MIN_STAKE:
        return {"skip": True, "reason": f"Insufficient balance: ${balance:.2f}"}

    if not sl_pct or sl_pct <= 0:
        return {"skip": True, "reason": "Invalid SL percentage"}

    perf         = _get_recent_performance()
    drawdown     = _get_drawdown(balance)
    total_trades = _get_total_closed_trades()

    base_risk = PAPER_BASE_RISK if is_paper else LIVE_BASE_RISK

    risk_pct = _dynamic_risk(base_risk, perf, drawdown)
    risk_pct = risk_pct * _grade_mult(grade)
    risk_pct = risk_pct * _ml_mult(total_trades, ml_probability)
    risk_pct = risk_pct * _alignment_mult(alignment)
    risk_pct = risk_pct * _session_mult(session)
    risk_pct = max(MIN_RISK_PCT, min(MAX_RISK_PCT, risk_pct))

    leverage      = _leverage_from_sl(sl_pct, is_paper)
    risk_amt      = balance * risk_pct
    position_size = risk_amt / (sl_pct / 100)
    stake         = position_size / leverage
    max_stake     = balance * 0.20
    stake         = min(stake, max_stake)
    stake         = max(stake, MIN_STAKE)
    position_size = stake * leverage
    actual_risk   = position_size * (sl_pct / 100)

    win_rate    = perf.get("win_rate")
    streak      = perf.get("streak", 0)
    streak_type = perf.get("streak_type")

    return {
        "skip":          False,
        "risk_pct":      round(risk_pct * 100, 3),
        "risk_amt":      round(actual_risk, 4),
        "position_size": round(position_size, 4),
        "stake":         round(stake, 4),
        "leverage":      leverage,
        "drawdown_pct":  round(drawdown * 100, 2),
        "win_rate":      round(win_rate * 100, 1) if win_rate is not None else None,
        "streak":        streak,
        "streak_type":   streak_type,
        "today_pnl":     round(today_pnl, 4),
        "daily_limit":   round(daily_limit, 4),
        "open_trades":   open_counts["total"],
        "total_trades":  total_trades,
        "is_paper":      is_paper,
        "grade_mult":    round(_grade_mult(grade), 2),
        "ml_mult":       round(_ml_mult(total_trades, ml_probability), 2),
        "alignment_mult":round(_alignment_mult(alignment), 2),
        "session_mult":  round(_session_mult(session), 2),
        "session":       session,
        "alignment":     alignment.get("alignment", "none") if alignment else "none",
    }