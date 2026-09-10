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

SCORE_THRESHOLDS = {
    "aplus": 80,
    "a":     65,
    "b":     50,
}

COIN_CONFIG = {
    'ETH':  {'adx': 22, 'sl': 0.75, 'tp': 2.0,  'session': 'asia',   'skip_after_loss': False, 'tier': 1},
    'SOL':  {'adx': 22, 'sl': 1.0,  'tp': 3.5,  'session': 'london', 'skip_after_loss': False, 'tier': 1},
    'BNB':  {'adx': 25, 'sl': 0.5,  'tp': 1.5,  'session': 'ny',     'skip_after_loss': False, 'tier': 1},
    'DOGE': {'adx': 25, 'sl': 0.5,  'tp': 2.5,  'session': 'london', 'skip_after_loss': False, 'tier': 1},
    'AVAX': {'adx': 20, 'sl': 1.0,  'tp': 3.0,  'session': 'ny',     'skip_after_loss': False, 'tier': 2},
    'LINK': {'adx': 20, 'sl': 0.75, 'tp': 2.5,  'session': 'ny',     'skip_after_loss': False, 'tier': 1},
    'UNI':  {'adx': 15, 'sl': 0.75, 'tp': 3.5,  'session': 'london', 'skip_after_loss': False, 'tier': 1},
    'XRP':  {'adx': 25, 'sl': 0.5,  'tp': 2.0,  'session': 'london', 'skip_after_loss': True,  'tier': 1},
    'XLM':  {'adx': 25, 'sl': 0.5,  'tp': 3.5,  'session': 'london', 'skip_after_loss': False, 'tier': 1},
    'LTC':  {'adx': 25, 'sl': 0.75, 'tp': 1.5,  'session': 'london', 'skip_after_loss': False, 'tier': 1},
    'INJ':  {'adx': 22, 'sl': 0.75, 'tp': 3.0,  'session': 'london', 'skip_after_loss': False, 'tier': 2},
    'DOT':  {'adx': 15, 'sl': 1.0,  'tp': 2.0,  'session': 'ny',     'skip_after_loss': True,  'tier': 1},
    'OP':   {'adx': 15, 'sl': 1.0,  'tp': 2.0,  'session': 'asia',   'skip_after_loss': False, 'tier': 2},
    'ARB':  {'adx': 22, 'sl': 0.75, 'tp': 3.0,  'session': 'ny',     'skip_after_loss': True,  'tier': 1},
    'VET':  {'adx': 25, 'sl': 0.75, 'tp': 3.5,  'session': 'ny',     'skip_after_loss': False, 'tier': 1},
    'ETC':  {'adx': 18, 'sl': 0.75, 'tp': 2.0,  'session': 'london', 'skip_after_loss': True,  'tier': 1},
    'SEI':  {'adx': 25, 'sl': 0.75, 'tp': 2.5,  'session': 'london', 'skip_after_loss': False, 'tier': 1},
    'SUI':  {'adx': 25, 'sl': 1.5,  'tp': 2.5,  'session': 'ny',     'skip_after_loss': False, 'tier': 1},
}

REMOVED_COINS = ['BTC', 'ADA']

CRYPTO_CORRELATION_EFFECTIVE_N  = 1.9
CRYPTO_TOTAL_COINS               = 18
CRYPTO_POSITION_SIZE_MULTIPLIER  = round(CRYPTO_CORRELATION_EFFECTIVE_N / CRYPTO_TOTAL_COINS, 4)

CIRCUIT_BREAKER_CONFIG = {
    'coin_drop_4h_pct':        8.0,
    'daily_sl_pause_count':    3,
    'portfolio_dd_level1_pct': 5.0,
    'portfolio_dd_level2_pct': 10.0,
    'portfolio_dd_level3_pct': 15.0,
    'portfolio_dd_level4_pct': 20.0,
    'portfolio_dd_level5_pct': 30.0,
    'size_mult_level1':        0.7,
    'size_mult_level2':        0.4,
    'size_mult_level3':        0.2,
    'size_mult_level4':        0.0,
    'size_mult_level5':        0.0,
}

RS_CONFIG = {
    "cache_ttl_seconds":  900,
    "refresh_interval_m": 15,
    "high_tier_pct":      0.33,
    "medium_tier_pct":    0.33,
    "score_weights": {
        "relative_strength": 0.35,
        "volume_expansion":  0.25,
        "adx":               0.25,
        "momentum":          0.15,
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


def get_coin_config(coin: str) -> dict:
    return COIN_CONFIG.get(coin, {
        'adx':             18,
        'sl':              1.0,
        'tp':              2.5,
        'session':         'all',
        'skip_after_loss': False,
        'tier':            2,
    })


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
    ML_MIN_TRADES = 50
    ML_ENABLED    = False

    TWITTER_API_KEY       = os.getenv("TWITTER_API_KEY", "")
    TWITTER_API_SECRET    = os.getenv("TWITTER_API_SECRET", "")
    TWITTER_ACCESS_TOKEN  = os.getenv("TWITTER_ACCESS_TOKEN", "")
    TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")
    CONTENT_ENABLED       = os.getenv("CONTENT_ENABLED", "False").lower() == "true"
    CONTENT_AUTO_APPROVE  = os.getenv("CONTENT_AUTO_APPROVE", "False").lower() == "true"

    _FALLBACK_COINS: list = []

    TIMEFRAMES = ["1d", "4h", "1h"]

    TRADING_MODE  = os.getenv("TRADING_MODE", "paper")
    PAPER_TRADING = TRADING_MODE != "live"

    BALANCE_TIERS = [
        {"min": 0,    "max": 50,   "leverage": 5},
        {"min": 50,   "max": 200,  "leverage": 7},
        {"min": 200,  "max": 1000, "leverage": 10},
        {"min": 1000, "max": None, "leverage": 10},
    ]

    HYBRID_ENGINE = {
        "trend_min_adx":               18,
        "trend_ema_buffer_atr_mult":   0.05,
        "ema50_atr_mult":              3.0,
        "body_ratio_min":              0.5,
        "volume_ratio_min":            0.5,
        "sl_buffer_atr_mult":          0.5,
        "sl_min_pct":                  0.3,
        "sl_max_pct":                  5.0,
        "tp1_min_rr":                  2.0,
        "tp2_min_rr":                  4.0,
        "base_risk_pct":               0.01,
        "max_risk_pct":                0.02,
        "min_risk_pct":                0.005,
        "daily_loss_limit_pct":        0.02,
        "max_open_trades":             2,
        "max_same_direction":          1,
        "max_leverage":                10,
        "coin_cooldown_hours":         4,
        "grade_aplus":                 80,
        "grade_a":                     65,
        "grade_b":                     50,
        "grade_aplus_size_mult":       1.3,
        "grade_a_size_mult":           1.0,
        "grade_b_size_mult":           0.7,
        "entry_order_type":            "LIMIT",
        "limit_order_expiry_hours":    4,
        "regime_adx_trending":         25,
        "regime_adx_ranging":          20,
        "regime_size_trending":        1.0,
        "regime_size_ranging":         0.7,
        "regime_size_choppy":          0.5,
        "regime_size_volatile":        0.3,
        "funding_extreme_threshold":   0.0005,
    }

    SYSTEM_VERSION    = os.getenv("SYSTEM_VERSION",    "2.0.0")
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

    ANGELONE_CLIENT_ID   = os.getenv("ANGELONE_CLIENT_ID",   "")
    ANGELONE_API_KEY     = os.getenv("ANGELONE_API_KEY",     "")
    ANGELONE_PASSWORD    = os.getenv("ANGELONE_PASSWORD",    "")
    ANGELONE_TOTP_SECRET = os.getenv("ANGELONE_TOTP_SECRET", "")

    INDIAN_INSTRUMENTS: list = ["BANKNIFTY"]

    SESSION_COOKIE_NAME     = "se_user_token"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE   = True
    SESSION_COOKIE_SAMESITE = "lax"
    SESSION_COOKIE_MAX_AGE  = 60 * 60 * 24 * 7

    DEFAULT_TIER = TIER_FREE

    CAPITAL = float(os.getenv("CAPITAL", "1000"))

    RS_CACHE_TTL       = RS_CONFIG["cache_ttl_seconds"]
    RS_HIGH_TIER_PCT   = RS_CONFIG["high_tier_pct"]
    RS_MEDIUM_TIER_PCT = RS_CONFIG["medium_tier_pct"]

    TRACE_MAX_PER_COIN = DECISION_TRACE_CONFIG["max_traces_per_coin"]
    TRACE_REDIS_TTL    = DECISION_TRACE_CONFIG["redis_ttl_seconds"]

    WEIGHTS = {
        "momentum": 40,
        "trend":    30,
        "volume":   30,
    }

    MAX_WEIGHT = sum(WEIGHTS.values())

    @property
    def MIN_GRADE_TO_TRADE(self) -> list:
        return ["A+", "A", "B"]

    @property
    def COINS(self) -> list:
        global _coins_cache, _coins_cache_time
        if _coins_cache and (time.time() - _coins_cache_time) < _COINS_CACHE_TTL:
            return _coins_cache
        try:
            from database import SessionLocal, CoinConfig
            with SessionLocal() as db:
                rows = db.query(CoinConfig).filter(
                    CoinConfig.enabled == True,
                    CoinConfig.market  == "crypto",
                    CoinConfig.coin.notin_(REMOVED_COINS),
                ).all()
                if rows:
                    _coins_cache      = [r.coin for r in rows]
                    _coins_cache_time = time.time()
                    return _coins_cache
                return []
        except Exception:
            pass
        return [c for c in self._FALLBACK_COINS if c not in REMOVED_COINS]

    @COINS.setter
    def COINS(self, value: list) -> None:
        global _coins_cache, _coins_cache_time
        _coins_cache      = []
        _coins_cache_time = 0.0

    def get_coin_config(self, coin: str) -> dict:
        return get_coin_config(coin)

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

    def update_hybrid_parameter(self, key: str, value) -> None:
        if key in self.HYBRID_ENGINE:
            self.HYBRID_ENGINE[key] = value

    def get_hybrid_config(self) -> dict:
        return dict(self.HYBRID_ENGINE)

    def get_score_thresholds(self) -> dict:
        return dict(SCORE_THRESHOLDS)

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
        _ensure("SYSTEM_VERSION", "2.0.0")
        cfg.SYSTEM_VERSION = "2.0.0"
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