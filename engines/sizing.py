import logging
from datetime import date, datetime, timezone
from config import cfg

log = logging.getLogger(__name__)

SE = cfg.SCALP_ENGINE


def _get_recent_performance() -> dict:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).order_by(TradeModel.opened_at.desc()).limit(20).all()

        if not closed:
            return {"total": 0, "win_rate": None, "streak": 0, "streak_type": None}

        wins     = sum(1 for t in closed if t.outcome == "win")
        win_rate = wins / len(closed)
        streak   = 0
        streak_type = None

        for t in closed:
            if streak == 0:
                streak_type = t.outcome
                streak      = 1
            elif t.outcome == streak_type:
                streak += 1
            else:
                break

        return {"total": len(closed), "win_rate": win_rate, "streak": streak, "streak_type": streak_type}

    except Exception as e:
        log.error("_get_recent_performance: %s", e)
        return {"total": 0, "win_rate": None, "streak": 0, "streak_type": None}


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
            trades = db.query(TradeModel).filter(TradeModel.is_active == True).all()
        return {
            "total": len(trades),
            "long":  sum(1 for t in trades if t.direction == "LONG"),
            "short": sum(1 for t in trades if t.direction == "SHORT"),
        }
    except Exception as e:
        log.error("_get_open_trade_counts: %s", e)
        return {"total": 0, "long": 0, "short": 0}


def _leverage_from_sl(sl_pct: float) -> int:
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
    return min(lev, SE["max_leverage"])


def _grade_mult(grade: str) -> float:
    return {
        "A+": SE["grade_aplus_size_mult"],
        "A":  SE["grade_a_size_mult"],
        "B":  SE["grade_b_size_mult"],
    }.get(grade, SE["grade_b_size_mult"])


def calculate(
    balance:   float,
    sl_pct:    float,
    sl_dist:   float,
    grade:     str,
    direction: str,
) -> dict:

    today_pnl = _get_today_pnl()
    if today_pnl < -(balance * SE["daily_loss_limit_pct"]):
        return {"skip": True, "reason": "daily_loss_limit"}

    open_counts = _get_open_trade_counts()
    if open_counts["total"] >= SE["max_open_trades"]:
        return {"skip": True, "reason": "max_open_trades"}

    same_dir = open_counts["long"] if direction == "LONG" else open_counts["short"]
    if same_dir >= SE["max_same_direction"]:
        return {"skip": True, "reason": "max_same_direction"}

    perf     = _get_recent_performance()
    drawdown = _get_drawdown(balance)

    win_rate    = perf["win_rate"]
    streak      = perf["streak"]
    streak_type = perf["streak_type"]
    total       = perf["total"]

    if win_rate is None or total < 10:
        wr_mult = 0.8
    elif win_rate > 0.60:
        wr_mult = 1.2
    elif win_rate > 0.50:
        wr_mult = 1.0
    elif win_rate > 0.40:
        wr_mult = 0.85
    else:
        wr_mult = 0.65

    if drawdown > 0.15:
        dd_mult = 0.40
    elif drawdown > 0.10:
        dd_mult = 0.65
    elif drawdown > 0.05:
        dd_mult = 0.85
    else:
        dd_mult = 1.0

    if streak_type == "loss" and streak >= 3:
        streak_mult = 0.70
    elif streak_type == "loss" and streak == 2:
        streak_mult = 0.85
    elif streak_type == "win" and streak >= 4:
        streak_mult = 1.10
    else:
        streak_mult = 1.0

    base_risk = SE["base_risk_pct"]
    risk_pct  = base_risk * wr_mult * dd_mult * streak_mult * _grade_mult(grade)
    risk_pct  = max(SE["min_risk_pct"], min(SE["max_risk_pct"], risk_pct))

    risk_amt      = balance * risk_pct
    leverage      = _leverage_from_sl(sl_pct)
    position_size = risk_amt / (sl_dist / (sl_pct / 100 * balance / risk_amt))
    position_size = risk_amt / (sl_pct / 100)
    stake         = position_size / leverage
    max_stake     = balance * 0.20
    stake         = min(stake, max_stake)
    stake         = max(stake, 5.0)
    position_size = stake * leverage
    actual_risk   = position_size * (sl_pct / 100)

    return {
        "skip":          False,
        "risk_pct":      round(risk_pct * 100, 3),
        "risk_amt":      round(actual_risk, 4),
        "position_size": round(position_size, 4),
        "stake":         round(stake, 4),
        "leverage":      leverage,
        "wr_mult":       round(wr_mult, 2),
        "dd_mult":       round(dd_mult, 2),
        "streak_mult":   round(streak_mult, 2),
        "grade_mult":    round(_grade_mult(grade), 2),
        "drawdown_pct":  round(drawdown * 100, 2),
        "win_rate":      round(win_rate * 100, 1) if win_rate is not None else None,
        "today_pnl":     round(today_pnl, 4),
        "open_trades":   open_counts["total"],
    }