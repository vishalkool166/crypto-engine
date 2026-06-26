import logging
import math
from datetime import datetime, timezone

log = logging.getLogger(__name__)


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
        total = float(data.get("total", 0))
        return total
    except Exception as e:
        log.error(f"get_live_balance error: {e}")
        return 0.0


async def get_portfolio_state() -> dict:
    try:
        from api.freqtrade import _ft_get
        status = await _ft_get("/status")
        if not status or not isinstance(status, list):
            return {"open_trades": 0, "long_count": 0, "short_count": 0, "total_exposure": 0.0, "daily_pnl": 0.0}

        long_count  = sum(1 for t in status if not t.get("is_short", False))
        short_count = sum(1 for t in status if t.get("is_short", False))
        total_exposure = sum(float(t.get("stake_amount", 0)) for t in status)
        daily_pnl = sum(float(t.get("profit_abs", 0)) for t in status)

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


def _score_multiplier(score: float) -> float:
    if score >= 90:
        return 1.0
    if score >= 80:
        return 0.85
    if score >= 68:
        return 0.70
    if score >= 52:
        return 0.50
    return 0.30


def _regime_multiplier(regime: dict) -> float:
    regime_type = regime.get("type", "unknown")
    if regime_type in ("trending-bull", "trending-bear"):
        return 1.0
    if regime_type == "expansion":
        return 0.90
    if regime_type == "weak-trend":
        return 0.65
    if regime_type == "ranging":
        return 0.40
    if regime_type == "chop":
        return 0.10
    return 0.30


def _volatility_multiplier(vol_profile: dict) -> float:
    vol_class = vol_profile.get("volatility_class", "normal")
    atr_pct   = float(vol_profile.get("atr_pct", 2.0))

    if vol_class == "high":
        return max(0.3, 1.0 - (atr_pct - 4.0) * 0.1)
    if vol_class == "low":
        return 0.7
    return 1.0


def _btc_multiplier(btc_score: float, max_btc_score: float) -> float:
    if max_btc_score <= 0:
        return 0.7
    ratio = btc_score / max_btc_score
    if ratio >= 0.85:
        return 1.0
    if ratio >= 0.65:
        return 0.85
    if ratio >= 0.40:
        return 0.65
    return 0.40


def _portfolio_multiplier(portfolio: dict, direction: str, balance: float) -> float:
    open_trades    = portfolio.get("open_trades", 0)
    long_count     = portfolio.get("long_count", 0)
    short_count    = portfolio.get("short_count", 0)
    total_exposure = portfolio.get("total_exposure", 0.0)
    daily_pnl      = portfolio.get("daily_pnl", 0.0)

    mult = 1.0

    if open_trades >= 4:
        mult *= 0.3
    elif open_trades == 3:
        mult *= 0.5
    elif open_trades == 2:
        mult *= 0.75
    elif open_trades == 1:
        mult *= 0.90

    if direction == "LONG" and long_count >= 2:
        mult *= 0.6
    elif direction == "SHORT" and short_count >= 2:
        mult *= 0.6

    if balance > 0:
        exposure_ratio = total_exposure / balance
        if exposure_ratio > 0.8:
            mult *= 0.3
        elif exposure_ratio > 0.6:
            mult *= 0.5
        elif exposure_ratio > 0.4:
            mult *= 0.75

    if balance > 0 and daily_pnl < 0:
        loss_ratio = abs(daily_pnl) / balance
        if loss_ratio > 0.05:
            mult *= 0.2
        elif loss_ratio > 0.03:
            mult *= 0.5
        elif loss_ratio > 0.01:
            mult *= 0.75

    return max(0.1, mult)


def _max_trades_allowed(regime: dict, portfolio: dict, daily_pnl: float, balance: float) -> int:
    regime_type = regime.get("type", "unknown")

    if regime_type == "chop":
        return 0
    if regime_type == "ranging":
        return 1
    if regime_type == "weak-trend":
        return 2
    if regime_type in ("trending-bull", "trending-bear", "expansion"):
        base = 4
    else:
        base = 2

    if balance > 0 and daily_pnl < 0:
        loss_ratio = abs(daily_pnl) / balance
        if loss_ratio > 0.05:
            return 0
        if loss_ratio > 0.03:
            base = min(base, 1)
        elif loss_ratio > 0.01:
            base = min(base, 2)

    return base


def _compute_base_risk(balance: float, score: float, regime: dict) -> float:
    if balance <= 0:
        return 0.0

    regime_type = regime.get("type", "unknown")

    if regime_type in ("trending-bull", "trending-bear") and score >= 85:
        base_pct = 0.025
    elif regime_type in ("trending-bull", "trending-bear"):
        base_pct = 0.020
    elif regime_type == "expansion":
        base_pct = 0.018
    elif regime_type == "weak-trend":
        base_pct = 0.012
    elif regime_type == "ranging":
        base_pct = 0.008
    else:
        base_pct = 0.005

    return balance * base_pct


async def compute_allocation(
    signal:      dict,
    wconf:       dict,
    regime:      dict,
    vol_profile: dict,
    direction:   str,
) -> dict:

    balance   = await get_live_balance()
    portfolio = await get_portfolio_state()

    if balance <= 0:
        log.warning("compute_allocation: balance is zero — skipping")
        return {"skip": True, "reason": "Zero balance"}

    score      = float(signal.get("score", 0))
    btc_score  = float(wconf.get("btc_score", 0))
    btc_max    = 8.0
    daily_pnl  = portfolio.get("daily_pnl", 0.0)

    max_trades = _max_trades_allowed(regime, portfolio, daily_pnl, balance)
    if portfolio.get("open_trades", 0) >= max_trades:
        log.info(f"compute_allocation: max trades reached ({max_trades}) for regime {regime.get('type')}")
        return {"skip": True, "reason": f"Max trades {max_trades} reached for current regime"}

    base_risk = _compute_base_risk(balance, score, regime)

    q_mult    = _score_multiplier(score)
    r_mult    = _regime_multiplier(regime)
    v_mult    = _volatility_multiplier(vol_profile)
    b_mult    = _btc_multiplier(btc_score, btc_max)
    p_mult    = _portfolio_multiplier(portfolio, direction, balance)

    final_risk = base_risk * q_mult * r_mult * v_mult * b_mult * p_mult

    entry  = float(signal.get("entry", 0))
    sl     = float(signal.get("sl", 0))

    if not entry or not sl or entry == sl:
        return {"skip": True, "reason": "Invalid entry or SL"}

    sl_dist_pct = abs(entry - sl) / entry
    if sl_dist_pct <= 0:
        return {"skip": True, "reason": "Zero SL distance"}

    pos_size = final_risk / sl_dist_pct

    adx      = float(vol_profile.get("adx", 20))
    atr_pct  = float(vol_profile.get("atr_pct", 2.0))

    if adx >= 40 and atr_pct < 3.0:
        leverage = 15
    elif adx >= 25:
        leverage = 10
    elif adx >= 18:
        leverage = 7
    else:
        leverage = 5

    stake = pos_size / leverage

    min_stake = 5.0
    if stake < min_stake:
        return {"skip": True, "reason": f"Stake ${stake:.2f} below minimum ${min_stake}"}

    if stake > balance * 0.95:
        stake    = balance * 0.95
        pos_size = stake * leverage

    log.info(
        f"compute_allocation: balance=${balance:.2f} score={score} "
        f"regime={regime.get('type')} base_risk=${base_risk:.2f} "
        f"multipliers q={q_mult:.2f} r={r_mult:.2f} v={v_mult:.2f} b={b_mult:.2f} p={p_mult:.2f} "
        f"final_risk=${final_risk:.2f} pos_size=${pos_size:.2f} stake=${stake:.2f} lev={leverage}x"
    )

    return {
        "skip":         False,
        "balance":      balance,
        "risk_amt":     round(final_risk, 4),
        "pos_size":     round(pos_size, 4),
        "stake":        round(stake, 4),
        "leverage":     leverage,
        "sl_dist_pct":  round(sl_dist_pct * 100, 4),
        "multipliers": {
            "quality":   q_mult,
            "regime":    r_mult,
            "volatility": v_mult,
            "btc":       b_mult,
            "portfolio": p_mult,
        },
        "max_trades_allowed": max_trades,
        "open_trades":        portfolio.get("open_trades", 0),
        "daily_pnl":          daily_pnl,
    }