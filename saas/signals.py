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

        radar = []
        for r in raw_results:
            market = r.get("market", {})
            sig    = r.get("signal", {})
            expl   = r.get("explanation", {})

            radar_item = {
                "coin":           r.get("coin",      "--"),
                "grade":          r.get("grade",     "F"),
                "direction":      r.get("direction", "--"),
                "score":          r.get("score",     0),
                "price":          market.get("price",    0),
                "change":         market.get("change24", 0),
                "funding":        round(market.get("funding", 0) * 100, 4),
                "tradeable":      r.get("grade") in ["A+", "A"] and r.get("direction") in ["LONG", "SHORT"],
                "regime":         r.get("regime",  "--"),
                "session":        r.get("session", "--"),
                "timestamp":      r.get("cached_at"),
            }

            features = get_tier_features(tier)

            if features.get("show_ml", False):
                radar_item["ml_probability"] = r.get("ml_probability")
                radar_item["actual_rr"]      = r.get("actual_rr", 0)
            else:
                radar_item["ml_probability"] = None
                radar_item["actual_rr"]      = None

            if features.get("show_thesis", False):
                radar_item["confidence"] = expl.get("confidence_label", "")
            else:
                radar_item["confidence"] = None

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
            sig  = r.get("signal",      {})
            expl = r.get("explanation", {})

            queue_item = {
                "coin":      r.get("coin",      "--"),
                "grade":     r.get("grade",     "?"),
                "direction": r.get("direction", "?"),
                "score":     r.get("score",     0),
                "regime":    r.get("regime",    "--"),
                "session":   r.get("session",   "--"),
                "timestamp": r.get("cached_at"),
            }

            features = get_tier_features(tier)

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
                queue_item["sl_pct"]   = None
                queue_item["risk_amt"] = None
                queue_item["stake"]    = None
                queue_item["leverage"] = None
                queue_item["_blurred"] = True

            if features.get("show_thesis", False):
                queue_item["thesis"]           = expl.get("thesis", "")
                queue_item["confidence_label"] = expl.get("confidence_label", "")
            else:
                queue_item["thesis"]           = None
                queue_item["confidence_label"] = None

            if features.get("show_ml", False):
                queue_item["ml_probability"] = r.get("ml_probability")
                queue_item["actual_rr"]      = r.get("actual_rr", 0)
            else:
                queue_item["ml_probability"] = None
                queue_item["actual_rr"]      = None

            queue.append(queue_item)

        return {
            "radar":     radar,
            "queue":     queue,
            "tier":      tier,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        log.error(f"get_signals_for_tier error: {e}")
        return {"radar": [], "queue": [], "tier": tier}


def get_coin_detail_for_tier(coin: str, tier: str) -> dict:
    try:
        from data.cache import cache
        from api.dashboard import get_coin_detail

        data = get_coin_detail(coin.upper())
        if not data:
            return {}

        features = get_tier_features(tier)

        if not features.get("show_levels", False):
            sig = data.get("signal", {})
            if sig:
                sig["entry"]    = None
                sig["sl"]       = None
                sig["tp1"]      = None
                sig["sl_pct"]   = None
                sig["risk_amt"] = None
                sig["stake"]    = None
                sig["leverage"] = None
            data["_blurred"] = True

        if not features.get("show_factors", False):
            data["factors"]       = []
            data["market_score"]  = None
            data["entry_score"]   = None
            data["btc_score"]     = None
            data["norm_score"]    = None

        if not features.get("show_thesis", False):
            data["thesis"]      = None
            data["confidence"]  = None

        if not features.get("show_ml", False):
            data["ml_probability"] = None
            data["actual_rr"]      = None

        return data

    except Exception as e:
        log.error(f"get_coin_detail_for_tier error: {e}")
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
        log.error(f"get_history_for_tier error: {e}")
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

        perf = get_performance()

        if not features.get("show_full_history", False):
            perf["equity_curve"] = perf.get("equity_curve", [])[:3]

        if not features.get("backtest_access", False):
            perf["_backtest_locked"] = True

        return perf

    except Exception as e:
        log.error(f"get_performance_for_tier error: {e}")
        return {}


def get_universe_for_tier(tier: str) -> list:
    try:
        from api.dashboard import get_universe
        features    = get_tier_features(tier)
        coins_limit = get_coins_limit(tier)

        universe = get_universe()

        if tier == TIER_FREE:
            universe = universe[:coins_limit]

        for coin in universe:
            if not features.get("show_levels", False):
                coin["grade"]     = coin.get("grade", "--")
                coin["score"]     = None
                coin["direction"] = "--"

        return universe

    except Exception as e:
        log.error(f"get_universe_for_tier error: {e}")
        return []


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

        if not features.get("show_positions", False):
            summary["tradeable_count"] = None

        return summary

    except Exception as e:
        log.error(f"get_summary_for_tier error: {e}")
        return {}


def get_dashboard_for_tier(tier: str) -> dict:
    try:
        from api.dashboard import get_ticker_bar

        summary     = get_summary_for_tier(tier)
        signals     = get_signals_for_tier(tier)
        history     = get_history_for_tier(tier)
        universe    = get_universe_for_tier(tier)
        performance = get_performance_for_tier(tier)
        ticker      = get_ticker_bar()

        features = get_tier_features(tier)

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
        log.error(f"get_dashboard_for_tier error: {e}")
        return {"type": "dashboard", "tier": tier}


def build_ws_payload_for_tier(tier: str, event_type: str = "dashboard") -> dict:
    try:
        if event_type == "ping":
            from api.dashboard import get_ticker_bar, get_summary
            from scheduler import get_next_scan_epoch

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
        log.error(f"build_ws_payload_for_tier error: {e}")
        return {"type": event_type, "tier": tier}