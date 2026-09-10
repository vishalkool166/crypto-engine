import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional
from config import cfg, get_coin_config, CRYPTO_POSITION_SIZE_MULTIPLIER, CIRCUIT_BREAKER_CONFIG

log = logging.getLogger(__name__)

HE             = cfg.HYBRID_ENGINE
MIN_STAKE      = 5.0
MAX_RISK_PCT   = 0.02
MIN_RISK_PCT   = 0.005
PAPER_BASE     = 0.015
LIVE_BASE      = 0.01
ML_MIN_TRADES  = 100
DAILY_LOSS_LIM = 0.02

SESSION_MULT = {
    "London/NY Overlap": 1.0,
    "London":            1.0,
    "New York":          1.0,
    "Asia":              0.5,
    "Off Hours":         0.0,
}

SESSION_MAP = {
    "london": "London",
    "ny":     "New York",
    "asia":   "Asia",
    "all":    None,
}


@dataclass
class SizingResult:
    skip:            bool
    reason:          str
    risk_pct:        float
    risk_amt:        float
    position_size:   float
    stake:           float
    leverage:        int
    drawdown_pct:    float
    win_rate:        Optional[float]
    streak:          int
    streak_type:     Optional[str]
    today_pnl:       float
    daily_limit:     float
    open_trades:     int
    total_trades:    int
    is_paper:        bool
    grade_mult:      float
    regime_mult:     float
    ml_mult:         float
    alignment_mult:  float
    session_mult:    float


def _get_current_session() -> str:
    hour = datetime.now(timezone.utc).hour
    if 8  <= hour < 13: return "London"
    if 13 <= hour < 17: return "London/NY Overlap"
    if 17 <= hour < 21: return "New York"
    if 0  <= hour < 8:  return "Asia"
    return "Off Hours"


def _session_matches(coin_session: str) -> bool:
    if not coin_session or coin_session == "all":
        return True
    current = _get_current_session().lower()
    coin_s  = coin_session.lower()
    if coin_s == "london" and "london" in current:
        return True
    if coin_s == "ny" and ("new york" in current or "overlap" in current):
        return True
    if coin_s == "asia" and "asia" in current:
        return True
    return False


def _get_circuit_breaker_multiplier() -> float:
    try:
        from database import SessionLocal, PortfolioSnapshot
        db = SessionLocal()
        try:
            latest = db.query(PortfolioSnapshot).order_by(
                PortfolioSnapshot.snapshot_at.desc()
            ).first()
            if not latest:
                return 1.0
            level = latest.circuit_level or 0
            mult_map = {
                0: 1.0,
                1: CIRCUIT_BREAKER_CONFIG['size_mult_level1'],
                2: CIRCUIT_BREAKER_CONFIG['size_mult_level2'],
                3: CIRCUIT_BREAKER_CONFIG['size_mult_level3'],
                4: CIRCUIT_BREAKER_CONFIG['size_mult_level4'],
                5: CIRCUIT_BREAKER_CONFIG['size_mult_level5'],
            }
            return mult_map.get(level, 0.0)
        finally:
            db.close()
    except Exception as e:
        log.warning("_get_circuit_breaker_multiplier: %s", e)
        return 1.0


def calculate(
    balance:        float,
    sl_pct:         float,
    sl_dist:        float,
    grade:          str,
    direction:      str,
    regime_mult:    float = 1.0,
    ml_probability: Optional[float] = None,
    alignment_mult: float = 1.0,
    session:        str   = "",
    coin:           str   = "",
) -> SizingResult:
    is_paper = cfg.PAPER_TRADING

    today_pnl   = _get_today_pnl()
    daily_limit = balance * DAILY_LOSS_LIM

    if today_pnl < -daily_limit:
        return _skipped(
            f"daily_loss_limit:${abs(today_pnl):.2f}_of_${daily_limit:.2f}",
            today_pnl   = today_pnl,
            daily_limit = daily_limit,
        )

    open_counts = _get_open_counts()

    if open_counts["total"] >= HE["max_open_trades"]:
        return _skipped("max_open_trades", today_pnl=today_pnl, daily_limit=daily_limit)

    same_dir = open_counts["long"] if direction == "LONG" else open_counts["short"]
    if same_dir >= HE["max_same_direction"]:
        return _skipped("max_same_direction", today_pnl=today_pnl, daily_limit=daily_limit)

    if not balance or balance < MIN_STAKE:
        return _skipped(f"insufficient_balance:${balance:.2f}", today_pnl=today_pnl, daily_limit=daily_limit)

    if not sl_pct or sl_pct <= 0:
        return _skipped("invalid_sl_pct", today_pnl=today_pnl, daily_limit=daily_limit)

    coin_cfg     = get_coin_config(coin) if coin else {}
    coin_session = coin_cfg.get("session", "all")

    if not _session_matches(coin_session):
        return _skipped(
            f"session_filter:{coin_session}_current:{_get_current_session()}",
            today_pnl   = today_pnl,
            daily_limit = daily_limit,
        )

    from engines.state import should_skip_after_loss
    if coin and should_skip_after_loss(coin):
        return _skipped(
            f"skip_after_loss:{coin}",
            today_pnl   = today_pnl,
            daily_limit = daily_limit,
        )

    circuit_mult = _get_circuit_breaker_multiplier()
    if circuit_mult == 0.0:
        return _skipped("circuit_breaker_halt", today_pnl=today_pnl, daily_limit=daily_limit)

    perf         = _get_performance()
    drawdown     = _get_drawdown(balance)
    total_trades = _get_total_trades()

    base_risk = PAPER_BASE if is_paper else LIVE_BASE
    risk_pct  = _dynamic_risk(base_risk, perf, drawdown)

    g_mult  = _grade_mult(grade)
    r_mult  = float(regime_mult)
    ml_mult = _ml_mult(total_trades, ml_probability)
    a_mult  = float(alignment_mult)

    current_session = _get_current_session()
    s_mult = SESSION_MULT.get(current_session, 1.0)

    corr_mult = CRYPTO_POSITION_SIZE_MULTIPLIER if coin else 1.0

    risk_pct = risk_pct * g_mult * r_mult * ml_mult * a_mult * s_mult * circuit_mult * corr_mult
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

    return SizingResult(
        skip           = False,
        reason         = "",
        risk_pct       = round(risk_pct * 100, 3),
        risk_amt       = round(actual_risk, 4),
        position_size  = round(position_size, 4),
        stake          = round(stake, 4),
        leverage       = leverage,
        drawdown_pct   = round(drawdown * 100, 2),
        win_rate       = round(perf["win_rate"] * 100, 1) if perf["win_rate"] is not None else None,
        streak         = perf["streak"],
        streak_type    = perf["streak_type"],
        today_pnl      = round(today_pnl, 4),
        daily_limit    = round(daily_limit, 4),
        open_trades    = open_counts["total"],
        total_trades   = total_trades,
        is_paper       = is_paper,
        grade_mult     = round(g_mult,  2),
        regime_mult    = round(r_mult,  2),
        ml_mult        = round(ml_mult, 2),
        alignment_mult = round(a_mult,  2),
        session_mult   = round(s_mult,  2),
    )


def _dynamic_risk(base: float, perf: dict, drawdown: float) -> float:
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
        streak_mult = 1.15 if streak >= 5 else 1.08 if streak >= 3 else 1.0
    elif streak_type == "loss":
        streak_mult = 0.80 if streak >= 2 else 0.90
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


def _grade_mult(grade: str) -> float:
    return {
        "A+": HE["grade_aplus_size_mult"],
        "A":  HE["grade_a_size_mult"],
        "B":  HE["grade_b_size_mult"],
    }.get(grade, HE["grade_b_size_mult"])


def _ml_mult(total_trades: int, ml_probability: Optional[float]) -> float:
    if total_trades < ML_MIN_TRADES or ml_probability is None:
        return 1.0
    if ml_probability >= 0.75:
        return 1.10
    if ml_probability >= 0.65:
        return 1.00
    if ml_probability >= 0.55:
        return 0.85
    return 0.70


def _leverage_from_sl(sl_pct: float, is_paper: bool) -> int:
    cap = HE["max_leverage"]
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


def _get_today_pnl() -> float:
    try:
        from database import SessionLocal, Trade as TradeModel
        today_start = datetime(
            date.today().year,
            date.today().month,
            date.today().day,
            tzinfo=timezone.utc,
        )
        with SessionLocal() as db:
            trades = db.query(TradeModel).filter(
                TradeModel.closed_at >= today_start,
                TradeModel.outcome.in_(["win", "loss"]),
            ).all()
        return sum(float(t.net_pnl or t.pnl or 0) for t in trades)
    except Exception as e:
        log.error("_get_today_pnl: %s", e)
        return 0.0


def _get_open_counts() -> dict:
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
        log.error("_get_open_counts: %s", e)
        return {"total": 0, "long": 0, "short": 0}


def _get_total_trades() -> int:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            return db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).count()
    except Exception:
        return 0


def _get_performance() -> dict:
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
        s_type   = None

        for t in closed:
            if streak == 0:
                s_type = t.outcome
                streak = 1
            elif t.outcome == s_type:
                streak += 1
            else:
                break

        return {
            "total":       len(closed),
            "win_rate":    win_rate,
            "streak":      streak,
            "streak_type": s_type,
        }
    except Exception as e:
        log.error("_get_performance: %s", e)
        return {"total": 0, "win_rate": None, "streak": 0, "streak_type": None}


def _get_drawdown(balance: float) -> float:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"]),
                TradeModel.net_pnl.isnot(None),
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


def _skipped(reason: str, today_pnl: float = 0.0, daily_limit: float = 0.0) -> SizingResult:
    return SizingResult(
        skip           = True,
        reason         = reason,
        risk_pct       = 0.0,
        risk_amt       = 0.0,
        position_size  = 0.0,
        stake          = 0.0,
        leverage       = 0,
        drawdown_pct   = 0.0,
        win_rate       = None,
        streak         = 0,
        streak_type    = None,
        today_pnl      = round(today_pnl, 4),
        daily_limit    = round(daily_limit, 4),
        open_trades    = 0,
        total_trades   = 0,
        is_paper       = cfg.PAPER_TRADING,
        grade_mult     = 0.0,
        regime_mult    = 0.0,
        ml_mult        = 0.0,
        alignment_mult = 0.0,
        session_mult   = 0.0,
    )