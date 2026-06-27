import logging
import math
import time
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

BOOTSTRAP_DEFAULTS = {
    "A+": 0.030,
    "A":  0.025,
    "B":  0.015,
    "C":  0.008,
    "F":  0.005,
}

TIERS = {
    0:  {"min_trades": 0,   "max_trades": 20,  "label": "Bootstrap"},
    1:  {"min_trades": 20,  "max_trades": 50,  "label": "Developing"},
    2:  {"min_trades": 50,  "max_trades": 100, "label": "Calibrating"},
    3:  {"min_trades": 100, "max_trades": 200, "label": "Dynamic"},
    4:  {"min_trades": 200, "max_trades": None,"label": "Full"},
}

DRAWDOWN_STATES = {
    "NORMAL":    {"max_dd": 0.05,  "size_mult": 1.00, "max_trades": 4, "leverage_mult": 1.00},
    "CAUTION":   {"max_dd": 0.10,  "size_mult": 0.75, "max_trades": 3, "leverage_mult": 0.85},
    "REDUCED":   {"max_dd": 0.15,  "size_mult": 0.50, "max_trades": 2, "leverage_mult": 0.70},
    "DEFENSIVE": {"max_dd": 1.00,  "size_mult": 0.25, "max_trades": 1, "leverage_mult": 0.50},
}

REGIME_LEVERAGE_CEILING = {
    "trending-bull": 20,
    "trending-bear": 20,
    "expansion":     15,
    "weak-trend":    10,
    "ranging":        7,
    "chop":           3,
    "unknown":        5,
}

GRADE_LEVERAGE_CEILING = {
    "A+": 20,
    "A":  15,
    "B":   8,
    "C":   5,
    "F":   3,
}

RR_MINIMUMS = {
    ("A+", "trending-bull"):  1.5,
    ("A+", "trending-bear"):  1.5,
    ("A+", "expansion"):      1.8,
    ("A+", "weak-trend"):     2.0,
    ("A",  "trending-bull"):  1.8,
    ("A",  "trending-bear"):  1.8,
    ("A",  "expansion"):      2.0,
    ("A",  "weak-trend"):     2.2,
    ("B",  "trending-bull"):  2.0,
    ("B",  "trending-bear"):  2.0,
    ("B",  "expansion"):      2.5,
    ("B",  "weak-trend"):     3.0,
}

RR_DEFAULT = 1.5

_perf_cache:     dict  = {}
_perf_cache_at:  float = 0.0
_PERF_CACHE_TTL: float = 300.0

_equity_cache:    dict  = {}
_equity_cache_at: float = 0.0
_EQUITY_CACHE_TTL: float = 60.0


async def get_live_balance() -> float:
    try:
        from api.freqtrade import _ft_get
        data = await _ft_get("/balance")
        if not data:
            return 0.0
        currencies = data.get("currencies", [])
        usdt = next((c for c in currencies if c.get("currency") == "USDT"), {})
        free = float(usdt.get("free", 0))
        if free > 0:
            return free
        return float(data.get("total", 0))
    except Exception as e:
        log.error(f"get_live_balance error: {e}")
        return 0.0


async def get_portfolio_state() -> dict:
    try:
        from api.freqtrade import _ft_get
        status = await _ft_get("/status")
        if not status or not isinstance(status, list):
            return {"open_trades": 0, "long_count": 0, "short_count": 0, "total_exposure": 0.0, "daily_pnl": 0.0}

        long_count     = sum(1 for t in status if not t.get("is_short", False))
        short_count    = sum(1 for t in status if t.get("is_short", False))
        total_exposure = sum(float(t.get("stake_amount", 0)) for t in status)
        daily_pnl      = sum(float(t.get("profit_abs", 0)) for t in status)

        return {
            "open_trades":    len(status),
            "long_count":     long_count,
            "short_count":    short_count,
            "total_exposure": total_exposure,
            "daily_pnl":      daily_pnl,
        }
    except Exception as e:
        log.error(f"get_portfolio_state error: {e}")
        return {"open_trades": 0, "long_count": 0, "short_count": 0, "total_exposure": 0.0, "daily_pnl": 0.0}


def _get_performance_data() -> dict:
    global _perf_cache, _perf_cache_at

    if _perf_cache and time.time() - _perf_cache_at < _PERF_CACHE_TTL:
        return _perf_cache

    try:
        from database import SessionLocal, Signal as SignalModel

        with SessionLocal() as db:
            closed = db.query(SignalModel).filter(
                SignalModel.outcome.in_(["win", "loss"]),
                SignalModel.pnl.isnot(None)
            ).all()

        if not closed:
            _perf_cache    = {}
            _perf_cache_at = time.time()
            return {}

        by_grade  = {}
        by_regime = {}

        for s in closed:
            grade  = s.grade  or "F"
            regime = s.regime or "unknown"

            if grade not in by_grade:
                by_grade[grade] = {"wins": [], "losses": [], "pnls": []}

            pnl = float(s.pnl or 0)
            by_grade[grade]["pnls"].append(pnl)

            if s.outcome == "win":
                by_grade[grade]["wins"].append(pnl)
            else:
                by_grade[grade]["losses"].append(abs(pnl))

            if regime not in by_regime:
                by_regime[regime] = {"wins": 0, "total": 0}
            by_regime[regime]["total"] += 1
            if s.outcome == "win":
                by_regime[regime]["wins"] += 1

        result = {
            "by_grade":   by_grade,
            "by_regime":  by_regime,
            "total":      len(closed),
        }

        _perf_cache    = result
        _perf_cache_at = time.time()
        return result

    except Exception as e:
        log.error(f"_get_performance_data error: {e}")
        return {}


def _get_equity_state(balance: float) -> dict:
    global _equity_cache, _equity_cache_at

    if _equity_cache and time.time() - _equity_cache_at < _EQUITY_CACHE_TTL:
        return _equity_cache

    try:
        from database import SessionLocal, Signal as SignalModel

        with SessionLocal() as db:
            closed = db.query(SignalModel).filter(
                SignalModel.outcome.in_(["win", "loss"]),
                SignalModel.pnl.isnot(None)
            ).order_by(SignalModel.timestamp.asc()).all()

        if not closed:
            result = {
                "state":        "NORMAL",
                "drawdown_pct": 0.0,
                "peak_equity":  balance,
                "current_equity": balance,
                "daily_loss_limit": _get_dynamic_daily_limit([], balance),
                "daily_volatility": 0.02,
            }
            _equity_cache    = result
            _equity_cache_at = time.time()
            return result

        equity      = balance
        peak        = balance
        max_dd      = 0.0
        daily_pnls  = {}

        for s in closed:
            pnl    = float(s.pnl or 0)
            equity += pnl
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

            if s.timestamp:
                day = s.timestamp.date().isoformat()
                daily_pnls[day] = daily_pnls.get(day, 0) + pnl

        daily_values = list(daily_pnls.values())

        if max_dd >= 0.15:
            state = "DEFENSIVE"
        elif max_dd >= 0.10:
            state = "REDUCED"
        elif max_dd >= 0.05:
            state = "CAUTION"
        else:
            state = "NORMAL"

        daily_limit = _get_dynamic_daily_limit(daily_values, balance)

        daily_std = 0.02
        if len(daily_values) >= 5:
            mean = sum(daily_values) / len(daily_values)
            variance = sum((x - mean) ** 2 for x in daily_values) / len(daily_values)
            daily_std = math.sqrt(variance) / balance if balance > 0 else 0.02

        result = {
            "state":            state,
            "drawdown_pct":     round(max_dd * 100, 2),
            "peak_equity":      round(peak, 4),
            "current_equity":   round(equity, 4),
            "daily_loss_limit": daily_limit,
            "daily_volatility": round(daily_std, 4),
        }

        _equity_cache    = result
        _equity_cache_at = time.time()
        return result

    except Exception as e:
        log.error(f"_get_equity_state error: {e}")
        return {
            "state":            "NORMAL",
            "drawdown_pct":     0.0,
            "peak_equity":      balance,
            "current_equity":   balance,
            "daily_loss_limit": 0.05,
            "daily_volatility": 0.02,
        }


def _get_dynamic_daily_limit(daily_pnls: list, balance: float) -> float:
    if len(daily_pnls) < 10:
        return 0.05

    losses     = [abs(p) / balance for p in daily_pnls if p < 0 and balance > 0]
    if not losses:
        return 0.05

    avg_loss   = sum(losses) / len(losses)
    max_loss   = max(losses)
    dynamic    = avg_loss * 2.5

    return round(min(max(dynamic, 0.03), 0.08), 4)


def _get_tier(total_trades: int) -> int:
    for tier, config in sorted(TIERS.items(), reverse=True):
        if total_trades >= config["min_trades"]:
            return tier
    return 0


def _calculate_kelly(grade: str, perf: dict) -> float:
    grade_data = perf.get("by_grade", {}).get(grade, {})
    wins       = grade_data.get("wins",   [])
    losses     = grade_data.get("losses", [])
    total      = len(wins) + len(losses)

    if total < 20:
        return BOOTSTRAP_DEFAULTS.get(grade, 0.02)

    win_rate = len(wins) / total
    avg_win  = sum(wins)   / len(wins)   if wins   else 0
    avg_loss = sum(losses) / len(losses) if losses else 0

    if avg_loss <= 0 or win_rate <= 0:
        return BOOTSTRAP_DEFAULTS.get(grade, 0.02)

    win_loss_ratio = avg_win / avg_loss
    kelly          = win_rate - (1 - win_rate) / win_loss_ratio
    half_kelly     = kelly / 2

    tier = _get_tier(total)

    if tier == 1:
        weight     = (total - 20) / 30
        blended    = BOOTSTRAP_DEFAULTS.get(grade, 0.02) * (1 - weight) + half_kelly * weight
        return round(max(0.005, min(0.06, blended)), 4)

    return round(max(0.005, min(0.06, half_kelly)), 4)


def _get_regime_win_rate(regime_type: str, perf: dict) -> float:
    regime_data = perf.get("by_regime", {}).get(regime_type, {})
    total       = regime_data.get("total", 0)
    wins        = regime_data.get("wins",  0)

    if total < 10:
        defaults = {
            "trending-bull": 0.65,
            "trending-bear": 0.65,
            "expansion":     0.55,
            "weak-trend":    0.50,
            "ranging":       0.40,
            "chop":          0.30,
        }
        return defaults.get(regime_type, 0.50)

    return wins / total


def _get_max_trades(
    regime:      dict,
    perf:        dict,
    equity_state: dict,
    daily_pnl:   float,
    balance:     float
) -> int:
    regime_type = regime.get("type", "unknown")

    if regime_type == "chop":
        return 0

    regime_wr = _get_regime_win_rate(regime_type, perf)

    if regime_wr >= 0.65:
        base = 4
    elif regime_wr >= 0.55:
        base = 3
    elif regime_wr >= 0.45:
        base = 2
    else:
        base = 1

    dd_state     = equity_state.get("state", "NORMAL")
    dd_config    = DRAWDOWN_STATES.get(dd_state, DRAWDOWN_STATES["NORMAL"])
    base         = min(base, dd_config["max_trades"])

    daily_limit  = equity_state.get("daily_loss_limit", 0.05)
    if balance > 0 and daily_pnl < 0:
        daily_used = abs(daily_pnl) / balance
        if daily_used >= daily_limit:
            return 0
        if daily_used >= daily_limit * 0.75:
            base = min(base, 1)

    return max(0, base)


def _get_correlation_multiplier(direction: str, portfolio: dict, coin: str) -> float:
    try:
        from database import SessionLocal, CoinConfig

        with SessionLocal() as db:
            row = db.query(CoinConfig).filter(CoinConfig.coin == coin).first()
            btc_corr = float(row.btc_correlation or 0.8) if row else 0.8

    except Exception:
        btc_corr = 0.8

    same_dir_count = (
        portfolio.get("long_count",  0) if direction == "LONG"
        else portfolio.get("short_count", 0)
    )

    if same_dir_count == 0:
        return 1.0

    penalty = btc_corr * same_dir_count * 0.20
    return round(max(0.30, 1.0 - penalty), 4)


def _get_funding_leverage_cap(funding: float) -> int:
    funding_pct = abs(funding) * 100

    if funding_pct > 0.10:
        return 5
    if funding_pct > 0.08:
        return 7
    if funding_pct > 0.05:
        return 10
    if funding_pct > 0.03:
        return 15
    return 20


def _get_atr_leverage_cap(atr_pct: float) -> int:
    if atr_pct > 6.0:
        return 5
    if atr_pct > 4.0:
        return 8
    if atr_pct > 2.5:
        return 12
    if atr_pct > 1.5:
        return 17
    return 20


def _calculate_leverage(
    adx:          float,
    atr_pct:      float,
    funding:      float,
    grade:        str,
    regime:       dict,
    equity_state: dict,
    score:        float,
) -> int:

    regime_type = regime.get("type", "unknown")

    if adx >= 40 and atr_pct < 2.0:
        base = 20
    elif adx >= 35 and atr_pct < 3.0:
        base = 17
    elif adx >= 25:
        base = 13
    elif adx >= 18:
        base = 9
    else:
        base = 6

    score_mult = (
        1.0  if score >= 85 else
        0.90 if score >= 68 else
        0.75 if score >= 52 else
        0.60
    )
    base = round(base * score_mult)

    regime_cap  = REGIME_LEVERAGE_CEILING.get(regime_type, 5)
    grade_cap   = GRADE_LEVERAGE_CEILING.get(grade, 5)
    funding_cap = _get_funding_leverage_cap(funding)
    atr_cap     = _get_atr_leverage_cap(atr_pct)

    dd_state    = equity_state.get("state", "NORMAL")
    dd_config   = DRAWDOWN_STATES.get(dd_state, DRAWDOWN_STATES["NORMAL"])
    dd_lev_mult = dd_config["leverage_mult"]

    leverage = min(base, regime_cap, grade_cap, funding_cap, atr_cap)
    leverage = round(leverage * dd_lev_mult)

    return max(3, leverage)


def _score_multiplier(score: float) -> float:
    if score >= 90: return 1.00
    if score >= 85: return 0.92
    if score >= 80: return 0.85
    if score >= 75: return 0.78
    if score >= 68: return 0.70
    if score >= 60: return 0.60
    if score >= 52: return 0.50
    return 0.35


def _volatility_multiplier(vol_profile: dict) -> float:
    vol_class = vol_profile.get("volatility_class", "normal")
    atr_pct   = float(vol_profile.get("atr_pct", 2.0))

    if vol_class == "high":
        return max(0.40, 1.0 - (atr_pct - 4.0) * 0.08)
    if vol_class == "low":
        return 0.75
    return 1.0


def _btc_multiplier(btc_score: float, max_btc_score: float) -> float:
    if max_btc_score <= 0:
        return 0.70
    ratio = btc_score / max_btc_score
    if ratio >= 0.85: return 1.00
    if ratio >= 0.65: return 0.88
    if ratio >= 0.40: return 0.70
    return 0.45


def _portfolio_multiplier(portfolio: dict, balance: float) -> float:
    open_trades    = portfolio.get("open_trades",    0)
    total_exposure = portfolio.get("total_exposure", 0.0)

    mult = 1.0

    if open_trades >= 4:
        mult *= 0.40
    elif open_trades == 3:
        mult *= 0.60
    elif open_trades == 2:
        mult *= 0.80
    elif open_trades == 1:
        mult *= 0.92

    if balance > 0:
        exposure_ratio = total_exposure / balance
        if exposure_ratio > 0.80:
            mult *= 0.35
        elif exposure_ratio > 0.60:
            mult *= 0.55
        elif exposure_ratio > 0.40:
            mult *= 0.78

    return max(0.10, mult)


def _get_max_position_cap(portfolio: dict, equity_state: dict) -> float:
    open_trades = portfolio.get("open_trades", 0)
    dd_state    = equity_state.get("state", "NORMAL")

    if open_trades == 0:
        base_cap = 0.28
    elif open_trades == 1:
        base_cap = 0.22
    elif open_trades == 2:
        base_cap = 0.17
    else:
        base_cap = 0.12

    dd_mults = {
        "NORMAL":    1.00,
        "CAUTION":   0.80,
        "REDUCED":   0.60,
        "DEFENSIVE": 0.40,
    }

    return base_cap * dd_mults.get(dd_state, 1.0)


def _get_min_rr(grade: str, regime: dict) -> float:
    regime_type = regime.get("type", "unknown")
    return RR_MINIMUMS.get((grade, regime_type), RR_DEFAULT)


def _get_max_sl_pct(atr_pct: float, regime: dict) -> float:
    regime_type = regime.get("type", "unknown")

    base = atr_pct * 2.5

    regime_caps = {
        "trending-bull": 10.0,
        "trending-bear": 10.0,
        "expansion":      9.0,
        "weak-trend":     7.0,
        "ranging":        6.0,
        "chop":           4.0,
    }

    cap = regime_caps.get(regime_type, 8.0)
    return min(base, cap)


async def _notify_skip(coin: str, direction: str, reason: str, details: dict):
    try:
        from alerts.telegram import send
        await send(
            f"🚫 *Trade Skipped — {coin} {direction}*\n\n"
            f"Reason: `{reason}`\n"
            f"Score: `{details.get('score', '--')}`\n"
            f"Grade: `{details.get('grade', '--')}`\n"
            f"Drawdown State: `{details.get('dd_state', '--')}`\n"
            f"Daily Used: `{details.get('daily_used_pct', '--')}%`"
        )
    except Exception as e:
        log.error(f"Skip notification error: {e}")


async def _notify_allocation(coin: str, direction: str, result: dict):
    try:
        from alerts.telegram import send
        mults = result.get("multipliers", {})
        await send(
            f"✅ *Trade Allocated — {coin} {direction}*\n\n"
            f"Grade: `{result.get('grade', '--')}` · Score: `{result.get('score', '--')}`\n"
            f"Kelly: `{result.get('kelly_pct', '--')}%` · Leverage: `{result.get('leverage', '--')}x`\n"
            f"Stake: `${result.get('stake', 0):.2f}` · Risk: `${result.get('risk_amt', 0):.2f}`\n"
            f"Drawdown State: `{result.get('dd_state', 'NORMAL')}`\n"
            f"Tier: `{result.get('tier_label', '--')}`\n\n"
            f"Multipliers: Q:`{mults.get('quality', '--')}` "
            f"R:`{mults.get('regime', '--')}` "
            f"V:`{mults.get('volatility', '--')}` "
            f"B:`{mults.get('btc', '--')}` "
            f"C:`{mults.get('correlation', '--')}` "
            f"DD:`{mults.get('drawdown', '--')}`"
        )
    except Exception as e:
        log.error(f"Allocation notification error: {e}")


async def compute_allocation(
    signal:      dict,
    wconf:       dict,
    regime:      dict,
    vol_profile: dict,
    direction:   str,
) -> dict:

    coin  = signal.get("coin", "")
    grade = signal.get("grade", "F")
    score = float(signal.get("score", 0))

    balance   = await get_live_balance()
    portfolio = await get_portfolio_state()

    if balance <= 0:
        log.warning("compute_allocation: balance is zero")
        return {"skip": True, "reason": "Zero balance"}

    perf         = _get_performance_data()
    equity_state = _get_equity_state(balance)
    total_trades = perf.get("total", 0)
    tier         = _get_tier(total_trades)
    tier_label   = TIERS[tier]["label"]
    dd_state     = equity_state.get("state", "NORMAL")
    dd_config    = DRAWDOWN_STATES.get(dd_state, DRAWDOWN_STATES["NORMAL"])
    daily_pnl    = portfolio.get("daily_pnl", 0.0)
    daily_limit  = equity_state.get("daily_loss_limit", 0.05)

    skip_details = {
        "score":         score,
        "grade":         grade,
        "dd_state":      dd_state,
        "daily_used_pct": round(abs(daily_pnl) / balance * 100, 2) if balance > 0 and daily_pnl < 0 else 0,
    }

    if balance > 0 and daily_pnl < 0:
        daily_used = abs(daily_pnl) / balance
        if daily_used >= daily_limit:
            reason = f"Daily loss limit hit: {daily_used*100:.1f}% of balance (limit: {daily_limit*100:.1f}%)"
            await _notify_skip(coin, direction, reason, skip_details)
            return {"skip": True, "reason": reason}

    max_trades = _get_max_trades(regime, perf, equity_state, daily_pnl, balance)

    if portfolio.get("open_trades", 0) >= max_trades:
        reason = f"Max trades {max_trades} reached for {regime.get('type', 'unknown')} regime"
        return {"skip": True, "reason": reason}

    entry     = float(signal.get("entry", 0))
    sl        = float(signal.get("sl",    0))
    actual_rr = float(signal.get("actual_rr", 0))
    funding   = float(signal.get("funding", 0))
    btc_score = float(wconf.get("btc_score", 0))
    atr_pct   = float(vol_profile.get("atr_pct", 2.0))
    adx       = float(vol_profile.get("adx", 20))

    if not entry or not sl or entry == sl:
        return {"skip": True, "reason": "Invalid entry or SL"}

    min_rr = _get_min_rr(grade, regime)
    if actual_rr < min_rr:
        reason = f"R:R {actual_rr:.2f} below minimum {min_rr} for {grade} in {regime.get('type', '--')}"
        await _notify_skip(coin, direction, reason, skip_details)
        return {"skip": True, "reason": reason}

    max_sl_pct = _get_max_sl_pct(atr_pct, regime)
    sl_dist_pct = abs(entry - sl) / entry * 100
    if sl_dist_pct > max_sl_pct:
        reason = f"SL distance {sl_dist_pct:.1f}% exceeds dynamic cap {max_sl_pct:.1f}%"
        await _notify_skip(coin, direction, reason, skip_details)
        return {"skip": True, "reason": reason}

    sl_dist_ratio = abs(entry - sl) / entry

    kelly_pct = _calculate_kelly(grade, perf)
    base_risk = balance * kelly_pct

    q_mult = _score_multiplier(score)
    v_mult = _volatility_multiplier(vol_profile)
    b_mult = _btc_multiplier(btc_score, 8.0)
    p_mult = _portfolio_multiplier(portfolio, balance)
    c_mult = _get_correlation_multiplier(direction, portfolio, coin)
    dd_mult = dd_config["size_mult"]

    daily_warning_mult = 1.0
    if balance > 0 and daily_pnl < 0:
        daily_used = abs(daily_pnl) / balance
        if daily_used >= daily_limit * 0.75:
            daily_warning_mult = 0.50

    final_risk = base_risk * q_mult * v_mult * b_mult * p_mult * c_mult * dd_mult * daily_warning_mult

    leverage = _calculate_leverage(
        adx          = adx,
        atr_pct      = atr_pct,
        funding      = funding,
        grade        = grade,
        regime       = regime,
        equity_state = equity_state,
        score        = score,
    )

    pos_size  = final_risk / sl_dist_ratio
    stake     = pos_size / leverage

    max_cap   = _get_max_position_cap(portfolio, equity_state)
    max_stake = balance * max_cap
    min_stake = 5.0

    if stake < min_stake:
        reason = f"Stake ${stake:.2f} below minimum ${min_stake}"
        return {"skip": True, "reason": reason}

    stake    = min(stake, max_stake)
    pos_size = stake * leverage

    result = {
        "skip":               False,
        "balance":            balance,
        "risk_amt":           round(final_risk, 4),
        "pos_size":           round(pos_size,   4),
        "stake":              round(stake,       4),
        "leverage":           leverage,
        "sl_dist_pct":        round(sl_dist_pct, 4),
        "kelly_pct":          round(kelly_pct * 100, 2),
        "tier":               tier,
        "tier_label":         tier_label,
        "dd_state":           dd_state,
        "drawdown_pct":       equity_state.get("drawdown_pct", 0),
        "daily_loss_limit":   round(daily_limit * 100, 2),
        "max_trades_allowed": max_trades,
        "open_trades":        portfolio.get("open_trades", 0),
        "daily_pnl":          daily_pnl,
        "grade":              grade,
        "score":              score,
        "multipliers": {
            "quality":     round(q_mult,            4),
            "volatility":  round(v_mult,            4),
            "btc":         round(b_mult,            4),
            "portfolio":   round(p_mult,            4),
            "correlation": round(c_mult,            4),
            "drawdown":    round(dd_mult,           4),
            "daily":       round(daily_warning_mult,4),
        },
    }

    await _notify_allocation(coin, direction, result)

    log.info(
        f"compute_allocation: {coin} {direction} "
        f"tier:{tier_label} dd:{dd_state} "
        f"kelly:{kelly_pct*100:.2f}% "
        f"leverage:{leverage}x stake:${stake:.2f} "
        f"risk:${final_risk:.2f} "
        f"mults q:{q_mult:.2f} v:{v_mult:.2f} b:{b_mult:.2f} "
        f"p:{p_mult:.2f} c:{c_mult:.2f} dd:{dd_mult:.2f}"
    )

    return result