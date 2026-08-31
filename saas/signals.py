import logging
import time
from datetime import datetime, timezone
from config import (
    cfg,
    TIER_FREE, TIER_PRO, TIER_ELITE, TIER_ADMIN,
    get_tier_features, tier_meets_minimum
)
from saas.tiers import (
    filter_signal_for_tier,
    apply_signal_delay,
    get_signals_limit,
    get_coins_limit,
)

log = logging.getLogger(__name__)


def get_signals_for_tier(tier: str) -> dict:
    try:
        from data.cache import cache

        coins       = cfg.COINS
        coins_limit = get_coins_limit(tier)

        if tier == TIER_FREE:
            coins = coins[:coins_limit]

        raw_results = []
        for coin in coins:
            cached = cache.get_raw(f"signal_{coin}")
            if cached:
                raw_results.append(cached)

        raw_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        if tier == TIER_FREE:
            raw_results = apply_signal_delay(raw_results, tier)

        signals_limit = get_signals_limit(tier)
        features      = get_tier_features(tier)

        radar = []
        for r in raw_results:
            market = r.get("market", {})
            sig    = r.get("signal", {})

            radar_item = {
                "coin":       r.get("coin",      "--"),
                "grade":      r.get("grade",     "F"),
                "direction":  r.get("direction", "--"),
                "score":      r.get("score",     0),
                "state":      r.get("state",     "idle"),
                "price":      market.get("price",    0),
                "change":     market.get("change24", 0),
                "change_pos": market.get("change_pos", True),
                "funding":    round(market.get("funding", 0) * 100, 4),
                "tradeable":  r.get("grade") in ["A+", "A", "B"] and
                              r.get("direction") in ["LONG", "SHORT"],
                "regime":     r.get("regime",  "--"),
                "adx":        r.get("adx",     0),
                "rsi":        r.get("rsi",     0),
                "reason":     r.get("reason",  ""),
                "timestamp":  r.get("cached_at"),
            }

            if not features.get("show_ml", False):
                radar_item["ml_probability"] = None

            radar.append(radar_item)

        queue = []
        tradeable = [
            r for r in raw_results
            if r.get("grade") in cfg.MIN_GRADE_TO_TRADE
            and r.get("direction") in ["LONG", "SHORT"]
        ]

        if tier == TIER_FREE:
            tradeable = tradeable[:signals_limit]

        for r in tradeable[:5]:
            sig = r.get("signal", {})

            queue_item = {
                "coin":      r.get("coin",      "--"),
                "grade":     r.get("grade",     "?"),
                "direction": r.get("direction", "?"),
                "score":     r.get("score",     0),
                "state":     r.get("state",     "idle"),
                "regime":    r.get("regime",    "--"),
                "adx":       r.get("adx",       0),
                "rsi":       r.get("rsi",       0),
                "timestamp": r.get("cached_at"),
            }

            if features.get("show_levels", False):
                queue_item["entry"]    = sig.get("entry")
                queue_item["sl"]       = sig.get("sl")
                queue_item["tp1"]      = sig.get("tp1")
                queue_item["sl_pct"]   = sig.get("sl_pct",   0)
                queue_item["risk_amt"] = sig.get("risk_amt", 0)
                queue_item["stake"]    = sig.get("stake",    0)
                queue_item["leverage"] = sig.get("leverage", 10)
            else:
                queue_item["entry"]    = None
                queue_item["sl"]       = None
                queue_item["tp1"]      = None
                queue_item["_blurred"] = True

            queue.append(queue_item)

        return {
            "radar":     radar,
            "queue":     queue,
            "tier":      tier,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        log.error("get_signals_for_tier error: %s", e)
        return {"radar": [], "queue": [], "tier": tier}


def get_summary_for_tier(tier: str) -> dict:
    try:
        from api.dashboard import get_summary
        features = get_tier_features(tier)
        summary  = get_summary()

        if not features.get("show_performance", False):
            summary["today_pnl"]    = None
            summary["today_trades"] = None
            summary["win_rate"]     = None
            summary["total_pnl"]    = None
            summary["wins"]         = None
            summary["losses"]       = None

        return summary

    except Exception as e:
        log.error("get_summary_for_tier error: %s", e)
        return {}


def get_history_for_tier(tier: str, limit: int = 20) -> list:
    try:
        from api.dashboard import get_history
        features = get_tier_features(tier)

        if not features.get("show_performance", False):
            return []

        history = get_history(limit=limit)

        if not features.get("show_full_history", False):
            history = history[:3]
            for item in history:
                item["entry_price"] = None
                item["exit_price"]  = None
                item["sl_price"]    = None
                item["tp1_price"]   = None
                item["risk_amt"]    = None

        return history

    except Exception as e:
        log.error("get_history_for_tier error: %s", e)
        return []


def get_performance_for_tier(tier: str) -> dict:
    try:
        from api.dashboard import get_performance
        features = get_tier_features(tier)

        if not features.get("show_performance", False):
            return {
                "_locked":  True,
                "_feature": "show_performance",
            }

        return get_performance()

    except Exception as e:
        log.error("get_performance_for_tier error: %s", e)
        return {}


def get_universe_for_tier(tier: str) -> list:
    try:
        from api.dashboard import get_universe
        features    = get_tier_features(tier)
        coins_limit = get_coins_limit(tier)

        universe = get_universe()

        if tier == TIER_FREE:
            universe = universe[:coins_limit]

        return universe

    except Exception as e:
        log.error("get_universe_for_tier error: %s", e)
        return []


def get_dashboard_for_tier(tier: str) -> dict:
    try:
        from api.dashboard import get_ticker_bar

        summary     = get_summary_for_tier(tier)
        signals     = get_signals_for_tier(tier)
        history     = get_history_for_tier(tier)
        universe    = get_universe_for_tier(tier)
        performance = get_performance_for_tier(tier)
        ticker      = get_ticker_bar()
        features    = get_tier_features(tier)

        return {
            "type":        "dashboard",
            "tier":        tier,
            "features":    features,
            "summary":     summary,
            "signals":     signals,
            "history":     history,
            "universe":    universe,
            "performance": performance,
            "ticker":      ticker,
            "timestamp":   datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        log.error("get_dashboard_for_tier error: %s", e)
        return {"type": "dashboard", "tier": tier}


def build_ws_payload_for_tier(tier: str, event_type: str = "dashboard") -> dict:
    try:
        if event_type == "ping":
            from api.dashboard import get_ticker_bar
            summary = get_summary_for_tier(tier)
            return {
                "type":    "ticker",
                "items":   get_ticker_bar(),
                "summary": {
                    "next_scan_epoch": summary.get("next_scan_epoch", 0),
                    "mode":            summary.get("mode",        "paper"),
                    "today_pnl":       summary.get("today_pnl",   None),
                    "today_pnl_pos":   summary.get("today_pnl_pos", True),
                    "today_trades":    summary.get("today_trades", None),
                    "coins_count":     summary.get("coins_count",  0),
                },
            }

        return get_dashboard_for_tier(tier)

    except Exception as e:
        log.error("build_ws_payload_for_tier error: %s", e)
        return {"type": event_type, "tier": tier}