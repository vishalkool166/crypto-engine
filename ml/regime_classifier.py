import logging
from datetime import datetime, timezone
from config import cfg, ADAPTATION_CONFIG

log = logging.getLogger(__name__)


def classify_current_regime() -> dict:
    try:
        from data.cache import cache
        from engines.indicators import calculate_all
        from data.store import load_candles

        btc_data = cache.get_raw("btc_4h_data")
        btc_adx  = float(btc_data.get("adx") or 0) if btc_data else 0.0
        btc_cls  = btc_data.get("trend", {}).get("cls", "neutral") if btc_data else "neutral"

        hour = datetime.now(timezone.utc).hour
        if 8  <= hour < 13: session = "London"
        elif 13 <= hour < 17: session = "London/NY Overlap"
        elif 17 <= hour < 21: session = "New York"
        elif 0  <= hour < 8:  session = "Asia"
        else:                  session = "Off Hours"

        if btc_adx >= 30:
            if btc_cls == "bull":
                regime = "trending_bull"
            elif btc_cls == "bear":
                regime = "trending_bear"
            else:
                regime = "trending_neutral"
        elif btc_adx >= 20:
            regime = "weak_trend"
        elif btc_adx >= 15:
            regime = "ranging"
        else:
            regime = "choppy"

        historical = get_regime_performance()
        current_perf = historical.get(regime, {})

        action = _get_regime_action(current_perf)

        return {
            "regime":       regime,
            "session":      session,
            "btc_adx":      btc_adx,
            "btc_direction":btc_cls,
            "action":       action,
            "win_rate":     current_perf.get("win_rate", None),
            "trade_count":  current_perf.get("total", 0),
            "size_mult":    _get_size_mult(action),
            "classified_at":datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        log.error("classify_current_regime: %s", e)
        return {
            "regime":  "unknown",
            "action":  "normal",
            "size_mult": 1.0,
        }


def get_regime_performance(min_trades: int = 5) -> dict:
    try:
        from database import SessionLocal, Trade as TradeModel

        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"]),
                TradeModel.regime_at_entry.isnot(None)
            ).all()

        if not closed:
            return {}

        by_regime: dict = {}
        for t in closed:
            regime = _normalize_regime(t.regime_at_entry or "unknown")
            if regime not in by_regime:
                by_regime[regime] = {"wins": 0, "losses": 0, "pnl": 0.0}
            by_regime[regime]["pnl"] += float(t.net_pnl or t.pnl or 0)
            if t.outcome == "win":
                by_regime[regime]["wins"] += 1
            else:
                by_regime[regime]["losses"] += 1

        result = {}
        for regime, stats in by_regime.items():
            total = stats["wins"] + stats["losses"]
            if total >= min_trades:
                wr = stats["wins"] / total
                result[regime] = {
                    "total":    total,
                    "wins":     stats["wins"],
                    "losses":   stats["losses"],
                    "win_rate": round(wr * 100, 1),
                    "wr_raw":   wr,
                    "pnl":      round(stats["pnl"], 4),
                    "action":   _get_regime_action({"win_rate": wr * 100}),
                }

        return result

    except Exception as e:
        log.error("get_regime_performance: %s", e)
        return {}


def get_session_performance(min_trades: int = 5) -> dict:
    try:
        from database import SessionLocal, Trade as TradeModel

        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"]),
                TradeModel.session_at_entry.isnot(None)
            ).all()

        if not closed:
            return {}

        by_session: dict = {}
        for t in closed:
            session = t.session_at_entry or "Unknown"
            if session not in by_session:
                by_session[session] = {"wins": 0, "losses": 0, "pnl": 0.0}
            by_session[session]["pnl"] += float(t.net_pnl or t.pnl or 0)
            if t.outcome == "win":
                by_session[session]["wins"] += 1
            else:
                by_session[session]["losses"] += 1

        result = {}
        for session, stats in by_session.items():
            total = stats["wins"] + stats["losses"]
            if total >= min_trades:
                wr = stats["wins"] / total
                result[session] = {
                    "total":    total,
                    "wins":     stats["wins"],
                    "losses":   stats["losses"],
                    "win_rate": round(wr * 100, 1),
                    "wr_raw":   wr,
                    "pnl":      round(stats["pnl"], 4),
                    "action":   _get_regime_action({"win_rate": wr * 100}),
                }

        return result

    except Exception as e:
        log.error("get_session_performance: %s", e)
        return {}


def should_trade_in_current_conditions() -> dict:
    try:
        regime_config = ADAPTATION_CONFIG["regime_thresholds"]
        min_trades    = regime_config["min_trades_for_regime"]

        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            total = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).count()

        if total < min_trades:
            return {
                "should_trade": True,
                "size_mult":    1.0,
                "reason":       f"Insufficient data ({total}/{min_trades}) — trading normally",
                "regime":       "unknown",
                "session":      "unknown",
            }

        current = classify_current_regime()
        regime  = current.get("regime", "unknown")
        session = current.get("session", "unknown")
        action  = current.get("action", "normal")

        regime_perf  = get_regime_performance()
        session_perf = get_session_performance()

        regime_action  = regime_perf.get(regime,  {}).get("action", "normal")
        session_action = session_perf.get(session, {}).get("action", "normal")

        final_action = _combine_actions(regime_action, session_action)
        size_mult    = _get_size_mult(final_action)
        should_trade = final_action != "avoid"

        regime_wr  = regime_perf.get(regime,   {}).get("win_rate", None)
        session_wr = session_perf.get(session,  {}).get("win_rate", None)

        reason_parts = []
        if regime_wr is not None:
            reason_parts.append(f"Regime '{regime}': {regime_wr:.1f}% WR")
        if session_wr is not None:
            reason_parts.append(f"Session '{session}': {session_wr:.1f}% WR")

        return {
            "should_trade":  should_trade,
            "size_mult":     size_mult,
            "action":        final_action,
            "regime":        regime,
            "session":       session,
            "regime_wr":     regime_wr,
            "session_wr":    session_wr,
            "btc_adx":       current.get("btc_adx", 0),
            "btc_direction": current.get("btc_direction", "neutral"),
            "reason":        " | ".join(reason_parts) if reason_parts else "Insufficient data",
        }

    except Exception as e:
        log.error("should_trade_in_current_conditions: %s", e)
        return {
            "should_trade": True,
            "size_mult":    1.0,
            "reason":       f"Error in regime check: {e}",
        }


def get_regime_recommendations() -> list:
    try:
        regime_config = ADAPTATION_CONFIG["regime_thresholds"]
        min_trades    = regime_config["min_trades_per_regime"]
        avoid_below   = regime_config["avoid_below_win_rate"]
        reduce_below  = regime_config["reduce_size_below_win_rate"]

        regime_perf  = get_regime_performance(min_trades=min_trades)
        session_perf = get_session_performance(min_trades=min_trades)

        recommendations = []

        for regime, stats in regime_perf.items():
            wr = stats["wr_raw"]
            if wr < avoid_below:
                recommendations.append({
                    "type":      "regime_avoid",
                    "target":    regime,
                    "win_rate":  stats["win_rate"],
                    "trades":    stats["total"],
                    "action":    "avoid",
                    "reason":    f"Regime '{regime}' WR {stats['win_rate']:.1f}% below {avoid_below*100:.0f}% threshold",
                })
            elif wr < reduce_below:
                recommendations.append({
                    "type":      "regime_reduce",
                    "target":    regime,
                    "win_rate":  stats["win_rate"],
                    "trades":    stats["total"],
                    "action":    "reduce_size",
                    "reason":    f"Regime '{regime}' WR {stats['win_rate']:.1f}% — reduce size 50%",
                })

        for session, stats in session_perf.items():
            wr = stats["wr_raw"]
            if wr < avoid_below:
                recommendations.append({
                    "type":      "session_avoid",
                    "target":    session,
                    "win_rate":  stats["win_rate"],
                    "trades":    stats["total"],
                    "action":    "avoid",
                    "reason":    f"Session '{session}' WR {stats['win_rate']:.1f}% below {avoid_below*100:.0f}% threshold",
                })
            elif wr < reduce_below:
                recommendations.append({
                    "type":      "session_reduce",
                    "target":    session,
                    "win_rate":  stats["win_rate"],
                    "trades":    stats["total"],
                    "action":    "reduce_size",
                    "reason":    f"Session '{session}' WR {stats['win_rate']:.1f}% — reduce size 50%",
                })

        return recommendations

    except Exception as e:
        log.error("get_regime_recommendations: %s", e)
        return []


def _normalize_regime(regime_str: str) -> str:
    r = regime_str.lower()
    if "bull" in r and ("trend" in r or "in trade" in r):
        return "trending_bull"
    if "bear" in r and ("trend" in r or "in trade" in r):
        return "trending_bear"
    if "chop" in r:
        return "choppy"
    if "rang" in r:
        return "ranging"
    if "scan" in r or "watch" in r:
        return "weak_trend"
    return "unknown"


def _get_regime_action(stats: dict) -> str:
    wr = stats.get("win_rate", 50)
    if isinstance(wr, float) and wr <= 1.0:
        wr = wr * 100

    regime_config = ADAPTATION_CONFIG["regime_thresholds"]
    avoid_below   = regime_config["avoid_below_win_rate"]  * 100
    reduce_below  = regime_config["reduce_size_below_win_rate"] * 100

    if wr < avoid_below:
        return "avoid"
    if wr < reduce_below:
        return "reduce_size"
    return "normal"


def _get_size_mult(action: str) -> float:
    return {
        "avoid":       0.0,
        "reduce_size": 0.5,
        "normal":      1.0,
    }.get(action, 1.0)


def _combine_actions(regime_action: str, session_action: str) -> str:
    priority = {"avoid": 0, "reduce_size": 1, "normal": 2}
    if priority.get(regime_action, 2) <= priority.get(session_action, 2):
        return regime_action
    return session_action