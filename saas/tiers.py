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
    rows = [
        {
            "feature":     "Signal delivery",
            "free":        "30 min delay",
            "pro":         "Live",
            "elite":       "Live",
            "free_bool":   None,
            "pro_bool":    None,
            "elite_bool":  None,
        },
        {
            "feature":    "Signals per day",
            "free":       "3",
            "pro":        "Unlimited",
            "elite":      "Unlimited",
            "free_bool":  None,
            "pro_bool":   None,
            "elite_bool": None,
        },
        {
            "feature":    "Grade (A+/A/B)",
            "free":       None,
            "pro":        None,
            "elite":      None,
            "free_bool":  True,
            "pro_bool":   True,
            "elite_bool": True,
        },
        {
            "feature":    "Entry / SL / TP",
            "free":       None,
            "pro":        None,
            "elite":      None,
            "free_bool":  False,
            "pro_bool":   True,
            "elite_bool": True,
        },
        {
            "feature":    "Signal thesis",
            "free":       None,
            "pro":        None,
            "elite":      None,
            "free_bool":  False,
            "pro_bool":   False,
            "elite_bool": True,
        },
        {
            "feature":    "Confluence factors",
            "free":       None,
            "pro":        None,
            "elite":      None,
            "free_bool":  False,
            "pro_bool":   False,
            "elite_bool": True,
        },
        {
            "feature":    "ML probability",
            "free":       None,
            "pro":        None,
            "elite":      None,
            "free_bool":  False,
            "pro_bool":   False,
            "elite_bool": True,
        },
        {
            "feature":    "Live positions",
            "free":       None,
            "pro":        None,
            "elite":      None,
            "free_bool":  False,
            "pro_bool":   True,
            "elite_bool": True,
        },
        {
            "feature":    "Performance history",
            "free":       "3 signals",
            "pro":        "Full",
            "elite":      "Full",
            "free_bool":  None,
            "pro_bool":   None,
            "elite_bool": None,
        },
        {
            "feature":    "Backtest access",
            "free":       None,
            "pro":        None,
            "elite":      None,
            "free_bool":  False,
            "pro_bool":   False,
            "elite_bool": True,
        },
        {
            "feature":    "API key",
            "free":       None,
            "pro":        None,
            "elite":      None,
            "free_bool":  False,
            "pro_bool":   False,
            "elite_bool": True,
        },
        {
            "feature":    "Coins monitored",
            "free":       "5",
            "pro":        "All",
            "elite":      "All",
            "free_bool":  None,
            "pro_bool":   None,
            "elite_bool": None,
        },
        {
            "feature":    "Support",
            "free":       "None",
            "pro":        "Email",
            "elite":      "Priority",
            "free_bool":  None,
            "pro_bool":   None,
            "elite_bool": None,
        },
    ]
    return rows


def _get_faq() -> list:
    return [
        {
            "question": "What is a signal?",
            "answer":   "A signal is a trading opportunity identified by our engine. It includes the coin, direction (LONG/SHORT), grade (A+/A/B), and for paid tiers — entry price, stop loss, and take profit levels.",
        },
        {
            "question": "How is the grade calculated?",
            "answer":   "Grades are based on a confluence score out of 100. A+ is 85+, A is 68+, B is 52+. The score combines 16 factors including market structure, liquidity sweeps, BTC alignment, session timing, and more.",
        },
        {
            "question": "What is the signal delay on the free plan?",
            "answer":   "Free plan signals are delayed by 30 minutes. Pro and Elite receive signals instantly as they are generated.",
        },
        {
            "question": "Can I cancel anytime?",
            "answer":   "Yes. Cancel anytime from your settings page. You keep access until the end of your billing period. No questions asked.",
        },
        {
            "question": "What exchanges are supported?",
            "answer":   "Signals are generated for Binance Futures (USDT perpetuals). The engine monitors multiple coins across multiple timeframes 24/7.",
        },
        {
            "question": "Is this financial advice?",
            "answer":   "No. Signal Engine provides automated technical analysis signals for educational purposes only. Always do your own research and never risk more than you can afford to lose.",
        },
        {
            "question": "How do I upgrade or downgrade?",
            "answer":   "Go to Settings → Subscription. Upgrades take effect immediately. Downgrades take effect at the end of your current billing period.",
        },
        {
            "question": "What is the confluence factor breakdown?",
            "answer":   "Elite users see exactly which of the 16 factors contributed to each signal score — including liquidity sweep, displacement, retest confirmation, BTC alignment, OI behavior, and more.",
        },
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