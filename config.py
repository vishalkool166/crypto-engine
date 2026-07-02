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
ENTRY_DEVIATION_MULT = 0.40
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

    @property
    def MIN_GRADE_TO_TRADE(self) -> list:
        if self.PAPER_TRADING:
            return ["A+", "A", "B"]
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

    if changed:
        log.info("[FIRST RUN] Secrets written to .env — visit /auth/setup to complete setup")

    if cfg.TRADING_MODE == "paper" and not cfg.is_demo_configured():
        log.warning("TRADING_MODE=paper but BINANCE_DEMO_API_KEY not set")

    if cfg.TRADING_MODE == "live" and not cfg.is_live_configured():
        log.warning("TRADING_MODE=live but BINANCE_API_KEY not set — switching to paper")
        cfg.TRADING_MODE  = "paper"
        cfg.PAPER_TRADING = True


cfg = Config()