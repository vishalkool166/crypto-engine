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

INDIAN_INSTRUMENTS_CONFIG = {
    'BANKNIFTY': {
        'direction':     'SHORT',
        'min_orb':       200,
        'max_orb':       350,
        'sl_mult':       0.3,
        'tp_mult':       1.0,
        'entry_buffer':  10,
        'min_pre_range': 300,
        'min_prev_range':600,
        'skip_weeks':    [3],
        'entry_start_h': 11,
        'entry_end_h':   12,
        'time_exit_h':   14,
        'time_exit_m':   30,
        'lot_size':      30,
    },
    'FINNIFTY': {
        'direction':     'LONG',
        'min_orb':       100,
        'max_orb':       250,
        'sl_mult':       0.25,
        'tp_mult':       1.0,
        'entry_buffer':  10,
        'min_pre_range': 200,
        'min_prev_range':400,
        'skip_weeks':    [3],
        'entry_start_h': 11,
        'entry_end_h':   12,
        'time_exit_h':   14,
        'time_exit_m':   30,
        'lot_size':      60,
    },
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










def get_coin_config(coin: str) -> dict:
    return COIN_CONFIG.get(coin, {
        'adx':             18,
        'sl':              1.0,
        'tp':              2.5,
        'session':         'all',
        'skip_after_loss': False,
        'tier':            2,
    })


def get_indian_instrument_config(instrument: str) -> dict:
    return INDIAN_INSTRUMENTS_CONFIG.get(instrument, INDIAN_INSTRUMENTS_CONFIG['BANKNIFTY'])


class Config:
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
    BINANCE_SECRET  = os.getenv("BINANCE_SECRET")

    BINANCE_DEMO_API_KEY  = os.getenv("BINANCE_DEMO_API_KEY")
    BINANCE_DEMO_SECRET   = os.getenv("BINANCE_DEMO_SECRET")
    BINANCE_DEMO_BASE_URL = os.getenv("BINANCE_DEMO_BASE_URL", "https://demo-fapi.binance.com")

    TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

    FINNHUB_KEY  = os.getenv("FINNHUB_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL   = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    DOMAIN       = os.getenv("ADMIN_APP_ORIGIN", "http://localhost:5174")

    PORT = int(os.getenv("PORT", 8000))
    ENV  = os.getenv("ENV", "development")

    TOTP_SECRET             = os.getenv("TOTP_SECRET", "")
    WEBHOOK_SECRET          = os.getenv("WEBHOOK_SECRET", "")

    REDIS_URL     = os.getenv("REDIS_URL", "redis://localhost:6379")
    ML_MIN_TRADES = 50
    ML_ENABLED    = False


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

    SYSTEM_VERSION    = os.getenv("SYSTEM_VERSION",    "3.0.0")
    ADAPTATION_FROZEN = os.getenv("ADAPTATION_FROZEN", "False").lower() == "true"

    GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

    ADMIN_EMAILS: list = [
        e.strip()
        for e in os.getenv("ADMIN_EMAILS", "operator@example.com").split(",")
        if e.strip()
    ]

    ANGELONE_CLIENT_ID   = os.getenv("ANGELONE_CLIENT_ID",   "")
    ANGELONE_API_KEY     = os.getenv("ANGELONE_API_KEY",     "")
    ANGELONE_PASSWORD    = os.getenv("ANGELONE_PASSWORD",    "")
    ANGELONE_TOTP_SECRET = os.getenv("ANGELONE_TOTP_SECRET", "")

    INDIAN_INSTRUMENTS: list = ["BANKNIFTY", "FINNIFTY"]

    SESSION_COOKIE_MAX_AGE  = 60 * 60 * 24 * 7



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
        return ["A+", "A"]

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

    def get_indian_instrument_config(self, instrument: str) -> dict:
        return get_indian_instrument_config(instrument)

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




cfg = Config()
