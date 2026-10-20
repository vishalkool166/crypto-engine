import logging
from datetime import datetime, timezone
from config import (
    cfg,
    TIER_FREE, TIER_PRO, TIER_ELITE, TIER_ADMIN,
    TIER_FEATURES, TIER_PRICING,
    tier_has_feature, tier_meets_minimum, get_tier_features
)

log = logging.getLogger(__name__)


def get_pricing_data() -> dict:
    return {
        "tiers": [
            {
                "id":            TIER_FREE,
                "name":          TIER_PRICING[TIER_FREE]["name"],
                "price_monthly": TIER_PRICING[TIER_FREE]["price_monthly"],
                "price_annual":  TIER_PRICING[TIER_FREE]["price_annual"],
                "description":   TIER_PRICING[TIER_FREE]["description"],
                "cta":           TIER_PRICING[TIER_FREE]["cta"],
                "popular":       TIER_PRICING[TIER_FREE]["popular"],
                "features":      _get_tier_feature_list(TIER_FREE),
            },
            {
                "id":            TIER_PRO,
                "name":          TIER_PRICING[TIER_PRO]["name"],
                "price_monthly": TIER_PRICING[TIER_PRO]["price_monthly"],
                "price_annual":  TIER_PRICING[TIER_PRO]["price_annual"],
                "description":   TIER_PRICING[TIER_PRO]["description"],
                "cta":           TIER_PRICING[TIER_PRO]["cta"],
                "popular":       TIER_PRICING[TIER_PRO]["popular"],
                "features":      _get_tier_feature_list(TIER_PRO),
            },
            {
                "id":            TIER_ELITE,
                "name":          TIER_PRICING[TIER_ELITE]["name"],
                "price_monthly": TIER_PRICING[TIER_ELITE]["price_monthly"],
                "price_annual":  TIER_PRICING[TIER_ELITE]["price_annual"],
                "description":   TIER_PRICING[TIER_ELITE]["description"],
                "cta":           TIER_PRICING[TIER_ELITE]["cta"],
                "popular":       TIER_PRICING[TIER_ELITE]["popular"],
                "features":      _get_tier_feature_list(TIER_ELITE),
            },
        ],
        "comparison": _get_comparison_table(),
        "faq":        _get_faq(),
    }


def _get_tier_feature_list(tier: str) -> list:
    features = get_tier_features(tier)
    result   = []

    delay = features.get("signal_delay_minutes", 0)
    if delay > 0:
        result.append({
            "text":      f"Signals delayed {delay} minutes",
            "available": True,
            "highlight": False,
        })
    else:
        result.append({
            "text":      "Live signals — zero delay",
            "available": True,
            "highlight": True,
        })

    limit = features.get("signals_per_day", 0)
    result.append({
        "text":      f"{limit if limit < 999 else 'Unlimited'} signals per day",
        "available": True,
        "highlight": False,
    })

    result.append({
        "text":      "Entry / SL / TP levels",
        "available": features.get("show_levels", False),
        "highlight": features.get("show_levels", False),
    })

    result.append({
        "text":      "Live positions view",
        "available": features.get("show_positions", False),
        "highlight": False,
    })

    result.append({
        "text":      "Full performance history",
        "available": features.get("show_full_history", False),
        "highlight": False,
    })

    result.append({
        "text":      "Signal thesis",
        "available": features.get("show_thesis", False),
        "highlight": False,
    })

    result.append({
        "text":      "Confluence factor breakdown",
        "available": features.get("show_factors", False),
        "highlight": features.get("show_factors", False),
    })

    result.append({
        "text":      "ML probability score",
        "available": features.get("show_ml", False),
        "highlight": False,
    })

    result.append({
        "text":      "Backtest access",
        "available": features.get("backtest_access", False),
        "highlight": False,
    })

    result.append({
        "text":      "API key access",
        "available": features.get("api_key_access", False),
        "highlight": False,
    })

    coins = features.get("coins_limit", 0)
    result.append({
        "text":      f"{coins if coins < 999 else 'All'} coins monitored",
        "available": True,
        "highlight": False,
    })

    return result


def _get_comparison_table() -> list:
    """Derive entitlements from the same configuration enforced by API routes."""
    plans = (TIER_FREE, TIER_PRO, TIER_ELITE)
    rows = [
        ("Entry / SL / TP", "show_levels"),
        ("Confluence factors", "show_factors"),
        ("Signal thesis", "show_thesis"),
        ("ML probability", "show_ml"),
        ("Positions", "show_positions"),
        ("Performance", "show_performance"),
        ("Full history", "show_full_history"),
        ("Backtesting", "backtest_access"),
        ("API key access", "api_key_access"),
    ]
    comparison = []
    for label, key in rows:
        entry = {"feature": label}
        for plan in plans:
            entry[plan] = None
            entry[f"{plan}_bool"] = bool(get_tier_features(plan)[key])
        comparison.append(entry)
    for label, field, formatter in (
        ("Signal delay", "signal_delay_minutes", lambda n: f"{n} min" if n else "Live"),
        ("Signals per day", "signals_per_day", lambda n: str(n) if n < 999 else "Up to 999"),
        ("Coins visible", "coins_limit", lambda n: str(n) if n < 999 else "All configured"),
    ):
        entry = {"feature": label}
        for plan in plans:
            entry[plan] = formatter(get_tier_features(plan)[field])
            entry[f"{plan}_bool"] = None
        comparison.append(entry)
    return comparison


def _get_faq() -> list:
    delay = get_tier_features(TIER_FREE)["signal_delay_minutes"]
    return [
        {"question": "What do plans control?", "answer":
         "Plans define signal visibility, history and analytics access. Trading execution is controlled separately by the engine."},
        {"question": "When can Basic users see signals?", "answer":
         f"Basic signals are configured with a {delay}-minute delay. Signal limits and eligibility are enforced by the backend."},
        {"question": "Can I upgrade from the dashboard?", "answer":
         "Automated subscription checkout is not enabled. Contact the administrator to request a plan change."},
        {"question": "Is Signal Engine financial advice?", "answer":
         "Signal Engine provides technical analysis for research and educational purposes, not personalized investment advice."},
    ]


def filter_signal_for_tier(signal: dict, tier: str) -> dict:
    if not signal:
        return signal

    features = get_tier_features(tier)
    filtered = dict(signal)

    if not features.get("show_levels", False):
        filtered["entry"]    = None
        filtered["sl"]       = None
        filtered["tp1"]      = None
        filtered["sl_pct"]   = None
        filtered["risk_amt"] = None
        filtered["stake"]    = None
        filtered["leverage"] = None
        filtered["_blurred"] = True

    if not features.get("show_factors", False):
        filtered["factors"]       = None
        filtered["factor_scores"] = None
        filtered["market_score"]  = None
        filtered["entry_score"]   = None
        filtered["btc_score"]     = None

    if not features.get("show_thesis", False):
        filtered["thesis"]             = None
        filtered["confidence_label"]   = None
        filtered["explanation"]        = None

    if not features.get("show_ml", False):
        filtered["ml_probability"] = None

    return filtered


def apply_signal_delay(signals: list, tier: str) -> list:
    features      = get_tier_features(tier)
    delay_minutes = features.get("signal_delay_minutes", 0)

    if delay_minutes == 0:
        return signals

    now     = datetime.now(timezone.utc)
    result  = []

    for sig in signals:
        ts = sig.get("timestamp")
        if not ts:
            continue
        try:
            if isinstance(ts, str):
                from datetime import datetime as dt
                sig_time = dt.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                sig_time = ts
            if sig_time.tzinfo is None:
                sig_time = sig_time.replace(tzinfo=timezone.utc)
            age_minutes = (now - sig_time).total_seconds() / 60
            if age_minutes >= delay_minutes:
                result.append(sig)
        except Exception as e:
            log.warning(f"Signal delay check error: {e}")
            continue

    return result


def get_signals_limit(tier: str) -> int:
    features = get_tier_features(tier)
    return features.get("signals_per_day", 3)


def get_coins_limit(tier: str) -> int:
    features = get_tier_features(tier)
    return features.get("coins_limit", 5)


def can_access_feature(tier: str, feature: str) -> bool:
    return tier_has_feature(tier, feature)


def get_upgrade_prompt(current_tier: str, required_tier: str, feature: str) -> dict:
    tier_names = {
        TIER_FREE:  "Basic",
        TIER_PRO:   "Pro",
        TIER_ELITE: "Elite",
    }
    feature_names = {
        "show_levels":       "Entry / SL / TP levels",
        "show_factors":      "Confluence factor breakdown",
        "show_thesis":       "Signal thesis",
        "show_ml":           "ML probability score",
        "show_positions":    "Live positions",
        "show_performance":  "Performance history",
        "backtest_access":   "Backtest access",
        "api_key_access":    "API key access",
    }
    return {
        "code":             "upgrade_required",
        "current_tier":     current_tier,
        "current_name":     tier_names.get(current_tier, current_tier),
        "required_tier":    required_tier,
        "required_name":    tier_names.get(required_tier, required_tier),
        "feature":          feature,
        "feature_name":     feature_names.get(feature, feature),
        "message":          f"{feature_names.get(feature, feature)} requires {tier_names.get(required_tier, required_tier)} plan",
        "upgrade_url":      "/pricing",
    }