from dotenv import load_dotenv, set_key
import os
import secrets
import time

load_dotenv()

ENV_FILE = ".env"

_coins_cache:      list  = []
_coins_cache_time: float = 0.0
_COINS_CACHE_TTL:  float = 30.0


def _ensure(key: str, value: str):
    os.environ[key] = value
    set_key(ENV_FILE, key, value)


class Config:
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
    BINANCE_SECRET  = os.getenv("BINANCE_SECRET")

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

    FREQTRADE_URL      = os.getenv("FREQTRADE_URL", "http://freqtrade:8080")
    FREQTRADE_USERNAME = os.getenv("FREQTRADE_USERNAME", "freqtrade")
    FREQTRADE_PASSWORD = os.getenv("FREQTRADE_PASSWORD", "")

    TWITTER_API_KEY       = os.getenv("TWITTER_API_KEY", "")
    TWITTER_API_SECRET    = os.getenv("TWITTER_API_SECRET", "")
    TWITTER_ACCESS_TOKEN  = os.getenv("TWITTER_ACCESS_TOKEN", "")
    TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")
    CONTENT_ENABLED       = os.getenv("CONTENT_ENABLED", "True").lower() == "true"
    CONTENT_AUTO_APPROVE  = os.getenv("CONTENT_AUTO_APPROVE", "False").lower() == "true"

    _FALLBACK_COINS = []

    TIMEFRAMES = ["1w", "1d", "4h", "1h"]

    CAPITAL  = float(os.getenv("CAPITAL", 16))
    LEVERAGE = 10

    RISK_PCT_PER_TRADE = 0.02
    DAILY_LOSS_CAP_PCT = 0.06
    MAX_TRADES_PER_DAY = 3
    TRADING_MODE       = os.getenv("TRADING_MODE", "paper")
    PAPER_TRADING      = TRADING_MODE != "live"

    BALANCE_TIERS = [
        {"min": 0,    "max": 50,   "risk_pct": 0.02, "max_trades": 2, "leverage": 10},
        {"min": 50,   "max": 200,  "risk_pct": 0.02, "max_trades": 2, "leverage": 10},
        {"min": 200,  "max": 1000, "risk_pct": 0.02, "max_trades": 3, "leverage": 15},
        {"min": 1000, "max": None, "risk_pct": 0.02, "max_trades": 3, "leverage": 20},
    ]

    B_GRADE_MARKET_SCORE_MIN = 65
    B_GRADE_BTC_SCORE_MIN    = 4

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
    def COINS(self, value: list):
        global _coins_cache, _coins_cache_time
        _coins_cache      = []
        _coins_cache_time = 0.0


def _bootstrap_secrets():
    import logging
    log = logging.getLogger(__name__)

    changed = False

    if not os.getenv("TOTP_SECRET"):
        import pyotp
        secret = pyotp.random_base32()
        _ensure("TOTP_SECRET", secret)
        cfg.TOTP_SECRET = secret
        log.info(f"[FIRST RUN] TOTP_SECRET generated: {secret}")
        changed = True

    if not os.getenv("DASHBOARD_API_KEY"):
        key = secrets.token_hex(32)
        _ensure("DASHBOARD_API_KEY", key)
        cfg.DASHBOARD_API_KEY = key
        log.info(f"[FIRST RUN] DASHBOARD_API_KEY generated: {key}")
        changed = True

    if not os.getenv("WEBHOOK_SECRET"):
        ws = secrets.token_hex(16)
        _ensure("WEBHOOK_SECRET", ws)
        cfg.WEBHOOK_SECRET = ws
        changed = True

    if not os.getenv("JWT_SECRET"):
        js = secrets.token_hex(32)
        _ensure("JWT_SECRET", js)
        cfg.JWT_SECRET = js
        changed = True

    if not os.getenv("DASHBOARD_USERNAME"):
        _ensure("DASHBOARD_USERNAME", "admin")
        cfg.DASHBOARD_USERNAME = "admin"
        changed = True

    if changed:
        log.info("[FIRST RUN] Secrets written to .env — visit /auth/setup to complete setup")


cfg = Config()