import logging
from datetime import date
from config import cfg

log = logging.getLogger(__name__)

MIN_STAKE          = 5.0
MAX_RISK_PCT       = 0.03
MIN_RISK_PCT       = 0.005
PAPER_LEVERAGE_CAP = 10
LIVE_LEVERAGE_CAP  = 20
PAPER_BASE_RISK    = 0.02
LIVE_BASE_RISK     = 0.01
ML_MIN_TRADES      = 100


async def _get_balance() -> float:
    try:
        from trade.exchange import get_balance
        balance = await get_balance()
        return float(balance.get("free", 0))
    except Exception as e:
        log.error(f"_get_balance error: {e}")
        return 0.0


async def _get_open_trades() -> list:
    try:
        from trade.monitor import _get_open_trades_from_db
        return _get_open_trades_from_db()
    except Exception as e:
        log.error(f"_get_open_trades error: {e}")
        return []


def _get_realized_daily_pnl() -> float:
    try:
        from database import SessionLocal, Signal as SignalModel
        today = date.today().isoformat()
        with SessionLocal() as db:
            sigs = db.query(SignalModel).filter(
                SignalModel.timestamp >= today,
                SignalModel.outcome.in_(["win", "loss"])
            ).all()
            return sum(float(s.pnl or 0) for s in sigs)
    except Exception as e:
        log.error(f"_get_realized_daily_pnl error: {e}")
        return 0.0


def _get_peak_and_drawdown(current_balance: float) -> tuple[float, float]:
    try:
        from database import SessionLocal, Signal as SignalModel
        with SessionLocal() as db:
            closed = db.query(SignalModel).filter(
                SignalModel.outcome.in_(["win", "loss"]),
                SignalModel.pnl.isnot(None)
            ).order_by(SignalModel.timestamp.asc()).all()

        if not closed:
            return current_balance, 0.0

        total_pnl = sum(float(s.pnl or 0) for s in closed)
        starting  = current_balance - total_pnl
        equity    = starting
        peak      = starting

        for s in closed:
            equity += float(s.pnl or 0)
            if equity > peak:
                peak = equity

        drawdown = (peak - current_balance) / peak if peak > 0 else 0.0
        return peak, max(0.0, drawdown)

    except Exception as e:
        log.error(f"_get_peak_and_drawdown error: {e}")
        return current_balance, 0.0


def _get_performance() -> dict:
    try:
        from database import SessionLocal, Signal as SignalModel
        with SessionLocal() as db:
            closed = db.query(SignalModel).filter(
                SignalModel.outcome.in_(["win", "loss"])
            ).order_by(SignalModel.timestamp.desc()).limit(20).all()

        if not closed:
            return {
                "total":       0,
                "win_rate":    None,
                "streak":      0,
                "streak_type": None,
            }

        wins     = sum(1 for s in closed if s.outcome == "win")
        win_rate = wins / len(closed)

        streak      = 0
        streak_type = None
        for s in closed:
            if streak == 0:
                streak_type = s.outcome
                streak      = 1
            elif s.outcome == streak_type:
                streak += 1
            else:
                break

        return {
            "total":       len(closed),
            "win_rate":    win_rate,
            "streak":      streak,
            "streak_type": streak_type,
        }

    except Exception as e:
        log.error(f"_get_performance error: {e}")
        return {"total": 0, "win_rate": None, "streak": 0, "streak_type": None}


def _get_total_closed_trades() -> int:
    try:
        from database import SessionLocal, Signal as SignalModel
        with SessionLocal() as db:
            return db.query(SignalModel).filter(
                SignalModel.outcome.in_(["win", "loss"])
            ).count()
    except Exception:
        return 0


def _dynamic_risk(base: float, perf: dict, drawdown: float) -> float:
    win_rate    = perf.get("win_rate")
    streak      = perf.get("streak", 0)
    streak_type = perf.get("streak_type")
    total       = perf.get("total", 0)

    if win_rate is None or total < 5:
        perf_mult = 1.0
    elif win_rate > 0.65:
        perf_mult = 1.30
    elif win_rate > 0.55:
        perf_mult = 1.10
    elif win_rate > 0.45:
        perf_mult = 1.00
    elif win_rate > 0.35:
        perf_mult = 0.80
    else:
        perf_mult = 0.60

    streak_mult = 1.0
    if streak_type == "win":
        if streak >= 5:
            streak_mult = 1.25
        elif streak >= 3:
            streak_mult = 1.15
    elif streak_type == "loss":
        if streak >= 5:
            streak_mult = 0.75
        elif streak >= 3:
            streak_mult = 0.85

    if drawdown > 0.25:
        dd_mult = 0.50
    elif drawdown > 0.15:
        dd_mult = 0.70
    elif drawdown > 0.10:
        dd_mult = 0.85
    else:
        dd_mult = 1.00

    risk = base * perf_mult * streak_mult * dd_mult
    return max(MIN_RISK_PCT, min(MAX_RISK_PCT, risk))


def _dynamic_leverage(atr_pct: float, adx: float, cap: int) -> int:
    if atr_pct > 5.0:
        low, high = 2, 4
    elif atr_pct > 3.0:
        low, high = 3, 6
    elif atr_pct > 2.0:
        low, high = 4, 8
    elif atr_pct > 1.0:
        low, high = 6, 12
    else:
        low, high = 8, 18

    if adx >= 40:
        leverage = high
    elif adx >= 25:
        leverage = round((low + high) / 2)
    else:
        leverage = low

    return max(2, min(leverage, cap))


def _dynamic_max_trades(drawdown: float, perf: dict, is_paper: bool) -> int:
    win_rate = perf.get("win_rate")
    total    = perf.get("total", 0)

    if is_paper:
        base = 3
    else:
        total_live = _get_total_closed_trades()
        if total_live < 50:
            base = 1
        elif total_live < 150:
            base = 2
        else:
            base = 3

    if win_rate is None or total < 5:
        return base

    if drawdown > 0.20:
        return max(1, base - 2)
    elif drawdown > 0.10:
        return max(1, base - 1)

    if win_rate > 0.60:
        return base
    elif win_rate > 0.45:
        return max(1, base - 1)
    else:
        return max(1, base - 2)


def _ml_mult(signal: dict, total_trades: int) -> float:
    if total_trades < ML_MIN_TRADES:
        return 1.0

    prob = signal.get("ml_probability")
    if prob is None:
        return 1.0

    if prob >= 0.75:
        return 1.10
    elif prob >= 0.65:
        return 1.00
    elif prob >= 0.55:
        return 0.85
    else:
        return 0.70


def _skip(reason: str) -> dict:
    log.info(f"Trade skipped: {reason}")
    return {"skip": True, "reason": reason}


async def compute_allocation(
    signal:      dict,
    wconf:       dict,
    regime:      dict,
    vol_profile: dict,
    direction:   str,
) -> dict:
    is_paper = cfg.PAPER_TRADING
    coin     = signal.get("coin", "UNKNOWN")
    grade    = signal.get("grade", "F")
    entry    = float(signal.get("entry", 0))
    sl       = float(signal.get("sl", 0))

    balance = await _get_balance()
    if balance < MIN_STAKE:
        return _skip(f"Insufficient balance: ${balance:.2f}")

    open_trades = await _get_open_trades()
    open_coins  = set(t.get("coin", "") for t in open_trades)

    if coin in open_coins:
        return _skip(f"{coin} already has an open trade")

    if not entry or not sl or entry == sl:
        return _skip("Invalid entry or SL")

    sl_distance = abs(entry - sl) / entry
    if sl_distance < 0.005:
        return _skip(f"SL too tight: {sl_distance*100:.2f}%")
    if sl_distance > 0.10:
        return _skip(f"SL too wide: {sl_distance*100:.2f}%")

    peak, drawdown = _get_peak_and_drawdown(balance)
    perf           = _get_performance()
    total_trades   = _get_total_closed_trades()

    if not is_paper:
        daily_pnl   = _get_realized_daily_pnl()
        daily_limit = balance * 0.03
        if daily_pnl < 0 and abs(daily_pnl) >= daily_limit:
            return _skip(
                f"Daily loss limit: ${abs(daily_pnl):.2f} "
                f"of ${daily_limit:.2f} limit"
            )

    max_trades = _dynamic_max_trades(drawdown, perf, is_paper)
    if len(open_trades) >= max_trades:
        return _skip(
            f"Max trades reached: {len(open_trades)}/{max_trades}"
        )

    base_risk  = PAPER_BASE_RISK if is_paper else LIVE_BASE_RISK
    lev_cap    = PAPER_LEVERAGE_CAP if is_paper else LIVE_LEVERAGE_CAP
    grade_mult = {"A+": 1.0, "A": 0.90, "B": 0.75}.get(grade, 0.50)

    risk_pct = _dynamic_risk(base_risk, perf, drawdown)
    risk_pct = risk_pct * grade_mult
    risk_pct = risk_pct * _ml_mult(signal, total_trades)
    risk_pct = max(MIN_RISK_PCT, min(MAX_RISK_PCT, risk_pct))

    atr_pct  = float(vol_profile.get("atr_pct", 2.0))
    adx      = float(vol_profile.get("adx", 20))
    leverage = _dynamic_leverage(atr_pct, adx, lev_cap)

    risk_amt      = balance * risk_pct
    position_size = risk_amt / sl_distance
    stake         = position_size / leverage
    max_stake     = balance * 0.25
    stake         = min(stake, max_stake)
    stake         = max(stake, MIN_STAKE)
    position_size = stake * leverage
    actual_risk   = position_size * sl_distance

    result = {
        "skip":               False,
        "coin":               coin,
        "grade":              grade,
        "balance":            round(balance, 2),
        "peak":               round(peak, 2),
        "drawdown_pct":       round(drawdown * 100, 2),
        "risk_pct":           round(risk_pct * 100, 3),
        "risk_amt":           round(actual_risk, 4),
        "pos_size":           round(position_size, 4),
        "stake":              round(stake, 4),
        "leverage":           leverage,
        "sl_dist_pct":        round(sl_distance * 100, 3),
        "atr_pct":            round(atr_pct, 3),
        "adx":                round(adx, 1),
        "open_trades":        len(open_trades),
        "max_trades_allowed": max_trades,
        "grade_mult":         grade_mult,
        "is_paper":           is_paper,
        "total_trades":       total_trades,
        "win_rate":           round(perf["win_rate"] * 100, 1) if perf["win_rate"] is not None else None,
        "streak":             perf["streak"],
        "streak_type":        perf["streak_type"],
    }

    log.info(
        f"Allocation: {coin} {direction} "
        f"{'PAPER' if is_paper else 'LIVE'} "
        f"balance:${balance:.2f} "
        f"dd:{drawdown*100:.1f}% "
        f"risk:{risk_pct*100:.2f}% "
        f"stake:${stake:.2f} "
        f"lev:{leverage}x "
        f"sl:{sl_distance*100:.2f}%"
    )

    await _notify_allocation(coin, direction, result)
    return result


async def _notify_allocation(coin: str, direction: str, r: dict):
    try:
        from alerts.telegram import send
        mode  = "PAPER" if r["is_paper"] else "LIVE"
        dd    = r["drawdown_pct"]
        emoji = "🟢" if dd < 10 else "🟡" if dd < 20 else "🔴"
        wr    = f"{r['win_rate']}%" if r["win_rate"] is not None else "N/A"

        await send(
            f"✅ *{coin} {direction} — {mode}*\n\n"
            f"{emoji} DD: `{dd}%` · WR: `{wr}`\n"
            f"Risk: `{r['risk_pct']}%` = `${r['risk_amt']:.2f}`\n"
            f"Stake: `${r['stake']:.2f}` × `{r['leverage']}x`\n"
            f"SL: `{r['sl_dist_pct']}%` · "
            f"ATR: `{r['atr_pct']}%` · ADX: `{r['adx']}`\n"
            f"Trades: `{r['open_trades']}/{r['max_trades_allowed']}`"
        )
    except Exception as e:
        log.error(f"Notify allocation error: {e}")


async def get_live_balance() -> float:
    return await _get_balance()


async def get_portfolio_state() -> dict:
    trades     = await _get_open_trades()
    open_count = len(trades)

    long_count  = sum(1 for t in trades if t.get("direction") == "LONG")
    short_count = sum(1 for t in trades if t.get("direction") == "SHORT")
    exposure    = sum(float(t.get("position_size") or 0) for t in trades)
    daily_pnl   = sum(float(t.get("profit_abs") or 0) for t in trades)

    return {
        "open_trades":    open_count,
        "long_count":     long_count,
        "short_count":    short_count,
        "total_exposure": exposure,
        "daily_pnl":      daily_pnl,
    }