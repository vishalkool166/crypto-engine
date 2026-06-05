from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    # Binance
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
    BINANCE_SECRET  = os.getenv("BINANCE_SECRET")

    # Telegram
    TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    # Finnhub
    FINNHUB_KEY = os.getenv("FINNHUB_KEY")

    # App
    PORT = int(os.getenv("PORT", 8000))
    ENV  = os.getenv("ENV", "development")

    # Coins
    TIER1 = ["BTC", "ETH", "BNB", "SOL", "XRP"]
    TIER2 = ["ADA", "AVAX", "LINK", "DOT", "DOGE", "LTC", "ATOM", "POL"]
    COINS = TIER1 + TIER2

    TIMEFRAMES = ["1w", "1d", "4h", "1h"]
    CAPITAL    = float(os.getenv("CAPITAL", 10))
    LEVERAGE   = 10

    # Grade filter
    MIN_GRADE_TO_TRADE = ["A+", "A"]

    # Risk
    RISK_PCT_PER_TRADE = 0.10
    DAILY_LOSS_CAP_PCT = 0.20
    MAX_TRADES_PER_DAY = 3

    # Signal thresholds
    GRADE_APLUS = 85
    GRADE_A     = 68
    GRADE_B     = 52
    GRADE_C     = 38

    # Weights
    WEIGHTS = {
        "liquidity_sweep":      12,
        "retest_confirmation":  12,
        "displacement":         11,
        "market_regime":        10,
        "weekly_filter":        10,
        "market_structure":      9,
        "session_timing":        8,
        "btc_alignment":         8,
        "oi_behavior":           7,
        "volume_expansion":      7,
        "funding_extreme":       6,
        "rsi_divergence":        4,
        "atr_volatility":        3,
        "rsi_context":           2,
        "macd_histogram":        1,
        "order_blocks":          4,
    }

    MAX_WEIGHT = sum(WEIGHTS.values())

    # Minimum conditions
    REQUIRE_SWEEP_OR_DISPLACEMENT = True
    REQUIRE_CANDLE_CLOSE          = True

    # Paper trading
    PAPER_TRADING = True

cfg = Config()