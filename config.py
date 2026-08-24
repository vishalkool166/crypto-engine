from dotenv import load_dotenv, set_key
import os
import secrets
import time

load_dotenv()

ENV_FILE = ".env"

_coins_cache:      list  = []
_coins_cache_time: float = 0.0
_COINS_CACHE_TTL:  float = 30.0

TAKER_FEE            = 0.0005
MAKER_FEE            = 0.0002
ORDER_FILL_TIMEOUT   = 60
ORDER_POLL_INTERVAL  = 3
MIN_STAKE_USDT       = 5.0
MAX_SIGNAL_AGE_HOURS = 4
ENTRY_DEVIATION_MULT = 0.10
ENTRY_FAVORABLE_MULT = 0.60

TIER_FREE  = "free"
TIER_PRO   = "pro"
TIER_ELITE = "elite"
TIER_ADMIN = "admin"

TIER_HIERARCHY = {
    TIER_FREE:  0,
    TIER_PRO:   1,
    TIER_ELITE: 2,
    TIER_ADMIN: 3,
}

TIER_FEATURES = {
    TIER_FREE: {
        "signal_delay_minutes": 30,
        "signals_per_day":      3,
        "show_levels":          False,
        "show_factors":         False,
        "show_thesis":          False,
        "show_ml":              False,
        "show_positions":       False,
        "show_performance":     False,
        "show_full_history":    False,
        "show_universe":        True,
        "show_system":          False,
        "api_key_access":       False,
        "backtest_access":      False,
        "coins_limit":          5,
    },
    TIER_PRO: {
        "signal_delay_minutes": 0,
        "signals_per_day":      999,
        "show_levels":          True,
        "show_factors":         False,
        "show_thesis":          False,
        "show_ml":              False,
        "show_positions":       True,
        "show_performance":     True,
        "show_full_history":    True,
        "show_universe":        True,
        "show_system":          False,
        "api_key_access":       False,
        "backtest_access":      False,
        "coins_limit":          999,
    },
    TIER_ELITE: {
        "signal_delay_minutes": 0,
        "signals_per_day":      999,
        "show_levels":          True,
        "show_factors":         True,
        "show_thesis":          True,
        "show_ml":              True,
        "show_positions":       True,
        "show_performance":     True,
        "show_full_history":    True,
        "show_universe":        True,
        "show_system":          False,
        "api_key_access":       True,
        "backtest_access":      True,
        "coins_limit":          999,
    },
    TIER_ADMIN: {
        "signal_delay_minutes": 0,
        "signals_per_day":      999,
        "show_levels":          True,
        "show_factors":         True,
        "show_thesis":          True,
        "show_ml":              True,
        "show_positions":       True,
        "show_performance":     True,
        "show_full_history":    True,
        "show_universe":        True,
        "show_system":          True,
        "api_key_access":       True,
        "backtest_access":      True,
        "coins_limit":          999,
    },
}

TIER_PRICING = {
    TIER_FREE: {
        "name":          "Basic",
        "price_monthly": 0,
        "price_annual":  0,
        "description":   "Delayed signals to get started",
        "cta":           "Start Free",
        "popular":       False,
    },
    TIER_PRO: {
        "name":          "Pro",
        "price_monthly": 29,
        "price_annual":  23,
        "description":   "Live signals with full entry levels",
        "cta":           "Start Pro",
        "popular":       True,
    },
    TIER_ELITE: {
        "name":          "Elite",
        "price_monthly": 79,
        "price_annual":  63,
        "description":   "Everything plus deep factor analysis",
        "cta":           "Start Elite",
        "popular":       False,
    },
}

ADAPTATION_CONFIG = {
    "hard_limits": {
        "max_risk_per_trade":    0.02,
        "max_daily_loss":        0.02,
        "max_concurrent_trades": 3,
        "max_leverage":          15,
        "min_sweep_score":       0.45,
        "min_zone_score":        0.45,
        "min_combined_score":    0.50,
        "max_sweep_age_hours":   4,
    },
    "soft_limits": {
        "sweep_min_score":       {"min": 0.45, "max": 0.70, "current": 0.45},
        "zone_min_score":        {"min": 0.45, "max": 0.70, "current": 0.45},
        "grade_a_threshold":     {"min": 0.55, "max": 0.75, "current": 0.65},
        "grade_aplus_threshold": {"min": 0.70, "max": 0.90, "current": 0.80},
        "sweep_max_age_hours":   {"min": 2,    "max": 6,    "current": 4},
        "base_risk_pct":         {"min": 0.005,"max": 0.015,"current": 0.010},
        "ml_threshold":          {"min": 0.55, "max": 0.80, "current": 0.65},
    },
    "change_rules": {
        "min_trades_before_change":        50,
        "min_win_rate_improvement":        0.03,
        "max_change_pct_per_cycle":        0.20,
        "min_days_between_changes":        7,
        "max_parameter_changes_per_month": 3,
        "rollback_review_trades":          20,
        "rollback_trigger_drop":           0.05,
        "require_human_approval":          True,
    },
    "regime_thresholds": {
        "min_trades_for_regime":      200,
        "min_trades_per_regime":      10,
        "avoid_below_win_rate":       0.40,
        "reduce_size_below_win_rate": 0.50,
    },
    "ml_thresholds": {
        "min_trades_for_training": 100,
        "retrain_every_n_trades":  50,
        "min_cv_auc":              0.60,
    },
    "analyzer_schedule": {
        "run_day":    "sunday",
        "run_hour":   0,
        "run_minute": 0,
    },
    "adapter_schedule": {
        "run_day":    "sunday",
        "run_hour":   1,
        "run_minute": 0,
    },
    "rollback_check_hour": 6,

    "pillar_weights": {
        "sweep":         0.25,
        "zone":          0.25,
        "structure":     0.20,
        "btc_alignment": 0.15,
        "regime":        0.15,
    },
    "pillar_limits": {
        "min_weight":        0.05,
        "max_weight":        0.50,
        "max_change":        0.05,
        "min_trades":        200,
        "min_failures":      20,
    },
    "thesis_time_limits": {
        "A+": 48.0,
        "A":  32.0,
        "B":  16.0,
    },
    "thesis_thresholds": {
        "hold":         0.80,
        "monitor":      0.60,
        "tighten":      0.40,
        "prepare_exit": 0.20,
        "exit":         0.00,
    },
}

RS_CONFIG = {
    "cache_ttl_seconds":   900,
    "refresh_interval_m":  15,
    "high_tier_pct":       0.33,
    "medium_tier_pct":     0.33,
    "score_weights": {
        "relative_strength": 0.35,
        "volume_expansion":  0.25,
        "adx":               0.25,
        "momentum":          0.15,
    },
    "score_caps": {
        "rs_max":       20,
        "rs_min":      -20,
        "vol_max":      15,
        "vol_min":     -10,
        "adx_max":      15,
        "momentum_max": 15,
        "momentum_min":-15,
    },
}

DECISION_TRACE_CONFIG = {
    "max_traces_per_coin": 10,
    "redis_ttl_seconds":   3600,
    "recent_list_size":    200,
}

REJECTION_STATS_CONFIG = {
    "live_ttl_days":  7,
    "daily_ttl_days": 90,
}

SCORE_THRESHOLDS = {
    "trending": {
        "aplus": 85,
        "a":     68,
        "b":     52,
    },
    "ranging": {
        "aplus": 78,
        "a":     62,
        "b":     48,
    },
    "choppy": {
        "aplus": 88,
        "a":     72,
        "b":     56,
    },
    "volatile": {
        "aplus": 90,
        "a":     75,
        "b":     58,
    },
    "default": {
        "aplus": 85,
        "a":     68,
        "b":     52,
    },
}

BTC_CONTEXT_SCORES = {
    "strongly_aligned":   10,
    "aligned":             7,
    "neutral":             5,
    "weakly_opposing":     0,
    "opposing":           -4,
    "strongly_opposing":  -8,
    "adx_strong_threshold": 30,
    "adx_moderate_threshold": 25,
    "adx_panic_threshold": 35,
}

HTF_ALIGNMENT_SCORES = {
    "both_aligned":    12,
    "one_aligned":      7,
    "both_neutral":     4,
    "one_opposing":    -5,
    "both_opposing":  -10,
}


def _ensure(key: str, value: str) -> None:
    os.environ[key] = value
    set_key(ENV_FILE, key, value)


def get_tier_features(tier: str) -> dict:
    return TIER_FEATURES.get(tier, TIER_FEATURES[TIER_FREE])


def tier_has_feature(tier: str, feature: str) -> bool:
    return bool(get_tier_features(tier).get(feature, False))


def tier_rank(tier: str) -> int:
    return TIER_HIERARCHY.get(tier, 0)


def tier_meets_minimum(user_tier: str, required_tier: str) -> bool:
    return tier_rank(user_tier) >= tier_rank(required_tier)


class Config:
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
    BINANCE_SECRET  = os.getenv("BINANCE_SECRET")

    BINANCE_DEMO_API_KEY  = os.getenv("BINANCE_DEMO_API_KEY")
    BINANCE_DEMO_SECRET   = os.getenv("BINANCE_DEMO_SECRET")
    BINANCE_DEMO_BASE_URL = os.getenv("BINANCE_DEMO_BASE_URL", "https://testnet.binancefuture.com")

    TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    FINNHUB_KEY  = os.getenv("FINNHUB_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    DOMAIN       = os.getenv("DOMAIN")

    PORT = int(os.getenv("PORT", 8000))
    ENV  = os.getenv("ENV", "development")

    TOTP_SECRET             = os.getenv("TOTP_SECRET", "")
    DASHBOARD_PASSWORD_HASH = os.getenv("DASHBOARD_PASSWORD_HASH", "")
    DASHBOARD_API_KEY       = os.getenv("DASHBOARD_API_KEY", "")
    DASHBOARD_USERNAME      = os.getenv("DASHBOARD_USERNAME", "admin")
    WEBHOOK_SECRET          = os.getenv("WEBHOOK_SECRET", "")
    JWT_SECRET              = os.getenv("JWT_SECRET", "")

    REDIS_URL     = os.getenv("REDIS_URL", "redis://localhost:6379")
    ML_MIN_TRADES = 100
    ML_ENABLED    = os.getenv("ML_ENABLED", "False").lower() == "true"

    TWITTER_API_KEY       = os.getenv("TWITTER_API_KEY", "")
    TWITTER_API_SECRET    = os.getenv("TWITTER_API_SECRET", "")
    TWITTER_ACCESS_TOKEN  = os.getenv("TWITTER_ACCESS_TOKEN", "")
    TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")
    CONTENT_ENABLED       = os.getenv("CONTENT_ENABLED", "True").lower() == "true"
    CONTENT_AUTO_APPROVE  = os.getenv("CONTENT_AUTO_APPROVE", "False").lower() == "true"

    _FALLBACK_COINS: list = []

    TIMEFRAMES = ["1w", "1d", "4h", "1h"]

    TRADING_MODE  = os.getenv("TRADING_MODE", "paper")
    PAPER_TRADING = TRADING_MODE != "live"

    BALANCE_TIERS = [
        {"min": 0,    "max": 50,   "leverage": 5},
        {"min": 50,   "max": 200,  "leverage": 7},
        {"min": 200,  "max": 1000, "leverage": 10},
        {"min": 1000, "max": None, "leverage": 15},
    ]

    B_GRADE_MARKET_SCORE_MIN = 65
    B_GRADE_BTC_SCORE_MIN    = 4
    B_GRADE_ENTRY_SCORE_MIN  = 50

    GRADE_APLUS = 85
    GRADE_A     = 68
    GRADE_B     = 52
    GRADE_C     = 38

    SESSION_HARD_FILTER = True

    MIN_WEEKLY_CANDLES = 200
    MIN_DAILY_CANDLES  = 200
    MIN_4H_CANDLES     = 200

    WEIGHTS = {
        "liquidity_sweep":     12,
        "retest_confirmation": 12,
        "displacement":        11,
        "market_regime":       10,
        "weekly_filter":       10,
        "market_structure":     9,
        "session_timing":       8,
        "btc_alignment":        8,
        "oi_behavior":          7,
        "volume_expansion":     7,
        "funding_extreme":      6,
        "rsi_divergence":       4,
        "atr_volatility":       3,
        "rsi_context":          2,
        "macd_histogram":       1,
        "order_blocks":         4,
    }

    MAX_WEIGHT = sum(WEIGHTS.values())

    REQUIRE_SWEEP_OR_DISPLACEMENT = True
    REQUIRE_CANDLE_CLOSE          = True

    RISK_PCT_PER_TRADE = 0.02

    SCALP_ENGINE = {
        "ema_period":                20,
        "ema_buffer_atr_mult":       0.3,

        "sweep_max_age_hours":       4,
        "sweep_min_wick_atr":        1.5,
        "sweep_min_score":           0.45,

        "zone_min_width_atr":        0.15,
        "zone_max_dist_atr":         4.0,
        "zone_max_touches":          1,
        "zone_min_score":            0.45,
        "zone_max_dist_pct":         1.0,

        "trigger_min_body_ratio":    0.55,
        "trigger_min_wick_ratio":    0.55,
        "trigger_min_score":         0.75,
        "trigger_lookback":          6,

        "sl_buffer_atr_mult":        1.0,
        "sl_min_pct":                0.50,
        "sl_max_pct":                4.0,

        "tp1_min_rr":                2.0,
        "tp2_min_rr":                3.5,

        "time_stop_hours":           6,
        "close_before_asia":         True,
        "tp1_close_pct":             0.65,
        "tp2_close_pct":             0.35,
        "time_stop_after_tp1_hours": 2,

        "base_risk_pct":             0.01,
        "max_risk_pct":              0.015,
        "min_risk_pct":              0.005,
        "daily_loss_limit_pct":      0.02,
        "max_open_trades":           2,
        "max_same_direction":        1,
        "max_leverage":              10,

        "coin_cooldown_hours":       4,

        "grade_aplus_threshold":     0.80,
        "grade_a_threshold":         0.65,
        "grade_b_threshold":         0.58,

        "grade_aplus_size_mult":     1.3,
        "grade_a_size_mult":         1.0,
        "grade_b_size_mult":         0.7,

        "kline_trigger_tf":          "1h",

        "entry_order_type":          "LIMIT",
        "limit_order_expiry_hours":  4,

        "min_adx":                   20,
    }

    THESIS_TIME_LIMITS = {
        "A+": 48.0,
        "A":  32.0,
        "B":  16.0,
    }

    THESIS_THRESHOLDS = {
        "hold":         0.80,
        "monitor":      0.60,
        "tighten":      0.40,
        "prepare_exit": 0.20,
        "exit":         0.00,
    }

    PILLAR_WEIGHTS_DEFAULT = {
        "sweep":         0.25,
        "zone":          0.25,
        "structure":     0.20,
        "btc_alignment": 0.15,
        "regime":        0.15,
    }

    SYSTEM_VERSION    = os.getenv("SYSTEM_VERSION",    "1.0.0")
    ADAPTATION_FROZEN = os.getenv("ADAPTATION_FROZEN", "False").lower() == "true"

    GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

    GITHUB_CLIENT_ID     = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")

    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

    ADMIN_EMAILS: list = [
        e.strip()
        for e in os.getenv("ADMIN_EMAILS", "").split(",")
        if e.strip()
    ]

    OAUTH_JWT_SECRET = os.getenv("OAUTH_JWT_SECRET", "")
    OAUTH_JWT_EXPIRY = int(os.getenv("OAUTH_JWT_EXPIRY_HOURS", "168"))

    SESSION_COOKIE_NAME     = "se_user_token"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE   = True
    SESSION_COOKIE_SAMESITE = "lax"
    SESSION_COOKIE_MAX_AGE  = 60 * 60 * 24 * 7

    DEFAULT_TIER = TIER_FREE

    CAPITAL = float(os.getenv("CAPITAL", "1000"))

    RS_CACHE_TTL        = RS_CONFIG["cache_ttl_seconds"]
    RS_HIGH_TIER_PCT    = RS_CONFIG["high_tier_pct"]
    RS_MEDIUM_TIER_PCT  = RS_CONFIG["medium_tier_pct"]

    TRACE_MAX_PER_COIN  = DECISION_TRACE_CONFIG["max_traces_per_coin"]
    TRACE_REDIS_TTL     = DECISION_TRACE_CONFIG["redis_ttl_seconds"]

    @property
    def MIN_GRADE_TO_TRADE(self) -> list:
        if self.PAPER_TRADING:
            return ["A+", "A"]
        return ["A+", "A"]

    @property
    def COINS(self) -> list:
        global _coins_cache, _coins_cache_time
        if _coins_cache and (time.time() - _coins_cache_time) < _COINS_CACHE_TTL:
            return _coins_cache
        try:
            from database import SessionLocal, CoinConfig
            with SessionLocal() as db:
                rows = db.query(CoinConfig).filter(CoinConfig.enabled == True).all()
                if rows:
                    _coins_cache      = [r.coin for r in rows]
                    _coins_cache_time = time.time()
                    return _coins_cache
                return []
        except Exception:
            pass
        return self._FALLBACK_COINS

    @COINS.setter
    def COINS(self, value: list) -> None:
        global _coins_cache, _coins_cache_time
        _coins_cache      = []
        _coins_cache_time = 0.0

    def is_admin_email(self, email: str) -> bool:
        return email.strip().lower() in [e.lower() for e in self.ADMIN_EMAILS]

    def is_demo_configured(self) -> bool:
        return bool(self.BINANCE_DEMO_API_KEY and self.BINANCE_DEMO_SECRET)

    def is_live_configured(self) -> bool:
        return bool(self.BINANCE_API_KEY and self.BINANCE_SECRET)

    def freeze_adaptations(self) -> None:
        self.ADAPTATION_FROZEN = True
        _ensure("ADAPTATION_FROZEN", "True")

    def unfreeze_adaptations(self) -> None:
        self.ADAPTATION_FROZEN = False
        _ensure("ADAPTATION_FROZEN", "False")

    def update_system_version(self, version: str) -> None:
        self.SYSTEM_VERSION = version
        _ensure("SYSTEM_VERSION", version)

    def update_scalp_parameter(self, key: str, value) -> None:
        if key in self.SCALP_ENGINE:
            self.SCALP_ENGINE[key] = value

    def update_thesis_time_limit(self, grade: str, hours: float) -> None:
        if grade in self.THESIS_TIME_LIMITS:
            self.THESIS_TIME_LIMITS[grade] = hours

    def update_thesis_threshold(self, level: str, value: float) -> None:
        if level in self.THESIS_THRESHOLDS:
            self.THESIS_THRESHOLDS[level] = value

    def get_thesis_time_limit(self, grade: str) -> float:
        return self.THESIS_TIME_LIMITS.get(grade, 32.0)

    def get_thesis_threshold(self, level: str) -> float:
        return self.THESIS_THRESHOLDS.get(level, 0.60)

    def get_adaptation_config(self) -> dict:
        return ADAPTATION_CONFIG

    def get_soft_limit(self, parameter: str) -> dict | None:
        return ADAPTATION_CONFIG["soft_limits"].get(parameter)

    def get_hard_limits(self) -> dict:
        return ADAPTATION_CONFIG["hard_limits"]

    def get_change_rules(self) -> dict:
        return ADAPTATION_CONFIG["change_rules"]

    def get_pillar_weights(self) -> dict:
        try:
            from ml.pillar_analyzer import get_current_weights
            return get_current_weights()
        except Exception:
            return dict(self.PILLAR_WEIGHTS_DEFAULT)

    def get_thesis_time_limits(self) -> dict:
        return dict(self.THESIS_TIME_LIMITS)

    def get_thesis_thresholds(self) -> dict:
        return dict(self.THESIS_THRESHOLDS)

    def get_score_thresholds(self, regime: str = "default") -> dict:
        r = (regime or "").lower()
        if "trend" in r:
            return SCORE_THRESHOLDS["trending"]
        if "rang" in r:
            return SCORE_THRESHOLDS["ranging"]
        if "chop" in r:
            return SCORE_THRESHOLDS["choppy"]
        if "volat" in r or "panic" in r:
            return SCORE_THRESHOLDS["volatile"]
        return SCORE_THRESHOLDS["default"]

    def get_btc_context_scores(self) -> dict:
        return dict(BTC_CONTEXT_SCORES)

    def get_htf_alignment_scores(self) -> dict:
        return dict(HTF_ALIGNMENT_SCORES)

    def get_rs_config(self) -> dict:
        return dict(RS_CONFIG)


def _bootstrap_secrets() -> None:
    import logging
    log = logging.getLogger(__name__)
    changed = False

    if not os.getenv("TOTP_SECRET"):
        import pyotp
        secret = pyotp.random_base32()
        _ensure("TOTP_SECRET", secret)
        cfg.TOTP_SECRET = secret
        log.info("[FIRST RUN] TOTP_SECRET generated: %s", secret)
        changed = True

    if not os.getenv("DASHBOARD_API_KEY"):
        key = secrets.token_hex(32)
        _ensure("DASHBOARD_API_KEY", key)
        cfg.DASHBOARD_API_KEY = key
        log.info("[FIRST RUN] DASHBOARD_API_KEY generated: %s", key)
        changed = True

    if not os.getenv("WEBHOOK_SECRET"):
        _ensure("WEBHOOK_SECRET", secrets.token_hex(16))
        cfg.WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
        changed = True

    if not os.getenv("JWT_SECRET"):
        _ensure("JWT_SECRET", secrets.token_hex(32))
        cfg.JWT_SECRET = os.getenv("JWT_SECRET", "")
        changed = True

    if not os.getenv("OAUTH_JWT_SECRET"):
        _ensure("OAUTH_JWT_SECRET", secrets.token_hex(32))
        cfg.OAUTH_JWT_SECRET = os.getenv("OAUTH_JWT_SECRET", "")
        changed = True

    if not os.getenv("DASHBOARD_USERNAME"):
        _ensure("DASHBOARD_USERNAME", "admin")
        cfg.DASHBOARD_USERNAME = "admin"
        changed = True

    if not os.getenv("TRADING_MODE"):
        _ensure("TRADING_MODE", "paper")
        cfg.TRADING_MODE  = "paper"
        cfg.PAPER_TRADING = True
        changed = True

    if not os.getenv("SYSTEM_VERSION"):
        _ensure("SYSTEM_VERSION", "1.0.0")
        cfg.SYSTEM_VERSION = "1.0.0"
        changed = True

    if changed:
        log.info("[FIRST RUN] Secrets written to .env — visit /auth/setup to complete setup")

    if cfg.TRADING_MODE == "paper" and not cfg.is_demo_configured():
        log.warning("TRADING_MODE=paper but BINANCE_DEMO_API_KEY not set")

    if cfg.TRADING_MODE == "live" and not cfg.is_live_configured():
        log.warning("TRADING_MODE=live but BINANCE_API_KEY not set — switching to paper")
        cfg.TRADING_MODE  = "paper"
        cfg.PAPER_TRADING = True


cfg = Config()