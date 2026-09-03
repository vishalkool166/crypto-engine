ANGELONE_API_LIMITS = {
    "loginByPassword": {
        "endpoint":   "/rest/auth/angelbroking/user/v1/loginByPassword",
        "per_second": 1,
        "per_minute": None,
        "per_hour":   None,
        "notes":      "One login per second max. We login once per day at 9:00 IST.",
    },
    "generateTokens": {
        "endpoint":   "/rest/auth/angelbroking/jwt/v1/generateTokens",
        "per_second": 1,
        "per_minute": None,
        "per_hour":   1000,
        "notes":      "Token refresh. We use loginByPassword not this endpoint.",
    },
    "getLtpData": {
        "endpoint":   "/rest/secure/angelbroking/order/v1/getLtpData",
        "per_second": 10,
        "per_minute": 500,
        "per_hour":   5000,
        "notes": (
            "USE THIS for live price during market hours. "
            "Returns ltp, open, high, low, close, volume in one call. "
            "At 5 minute refresh = 12 calls/hour = 0.24 percent of hourly limit. "
            "Safe to call every 1 minute if needed = 60 calls/hour = 1.2 percent."
        ),
    },
    "getCandleData": {
        "endpoint":   "/rest/secure/angelbroking/historical/v1/getCandleData",
        "per_second": 3,
        "per_minute": 180,
        "per_hour":   5000,
        "notes": (
            "USE THIS only for ORB setup at 9:35 IST once per day. "
            "Do NOT use for live price polling — use getLtpData instead. "
            "Max 100 candles per request for 15m timeframe. "
            "Rate limit resets every minute. "
            "If rate limited wait 2 minutes before retry. "
            "Bulk historical download: use 5 minute delay between chunks."
        ),
    },
    "getProfile": {
        "endpoint":   "/rest/secure/angelbroking/user/v1/getProfile",
        "per_second": 3,
        "per_minute": None,
        "per_hour":   1000,
        "notes":      "Not used in our system currently.",
    },
    "placeOrder": {
        "endpoint":   "/rest/secure/angelbroking/order/v1/placeOrder",
        "per_second": 20,
        "per_minute": 500,
        "per_hour":   1000,
        "notes":      "For future live order execution. Not used in paper trading.",
    },
}

SESSION_TTL_HOURS    = 24
SESSION_TTL_SECONDS  = SESSION_TTL_HOURS * 3600
OUR_REFRESH_HOUR_IST = 9
OUR_REFRESH_UTC      = "03:30"

RATE_LIMIT_WAIT_SECONDS = 120

OUR_USAGE = {
    "loginByPassword": {
        "frequency": "once per day at 9:00 IST",
        "calls_per_hour": 0.04,
        "limit_per_hour": None,
        "safe": True,
    },
    "getLtpData": {
        "frequency": "every 5 minutes during market hours",
        "calls_per_hour": 12,
        "limit_per_hour": 5000,
        "safe": True,
        "usage_pct": 0.24,
    },
    "getCandleData": {
        "frequency": "once per day at 9:35 IST for ORB setup",
        "calls_per_hour": 1,
        "limit_per_hour": 5000,
        "safe": True,
        "usage_pct": 0.02,
    },
}