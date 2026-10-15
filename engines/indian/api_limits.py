"""SmartAPI endpoint budgets; intentionally below the published ceilings.

Source: https://smartapi.angelone.in/docs (checked 2026-10-15).
The broker's documented limits are enforced by CLIENT CODE, not by server IP.
Place/modify/cancel share a cumulative 9/s budget. The endpoint is NOT a
promise that the broker will accept the request: 403/AB1021 can occur below it.
Conservative budgets are intentional and must not be raised without testing.
"""

# Hard maximums from Angel One; None = not published (never means unlimited).
ANGELONE_API_LIMITS = {
    "login": {"per_second": 1, "per_minute": None, "per_hour": None},
    "candles": {"per_second": 3, "per_minute": 150, "per_hour": 5000},
    "ltp": {"per_second": 10, "per_minute": 500, "per_hour": 5000},
    "quote": {"per_second": 10, "per_minute": 500, "per_hour": 5000},
    "order": {"per_second": 9, "per_minute": 500, "per_hour": 1000},
}

# The *local* pace and budgets are stricter than Angel One's published limits.
# A single shared Redis account namespace coordinates every backend worker.
# MIN_SPACING_SECONDS is a strict gap, independent of the rolling counters.
SAFE_BUDGETS = {
    "login": {"spacing": 60, "minute": 1, "hour": 15},
    "candles": {"spacing": 5, "minute": 100, "hour": 3500},
    "ltp": {"spacing": 0.2, "minute": 400, "hour": 4000},
    "quote": {"spacing": 0.2, "minute": 400, "hour": 4000},
    "order": {"spacing": 0.125, "minute": 400, "hour": 800},
}

# Historical APIs have repeatedly been reported as throttled *below* published
# limits. Do not auto-retry those failures; open a longer, endpoint-specific
# circuit, preserve cached information, and surface the incident to operators.
RATE_LIMIT_COOLDOWNS = {"candles": 600, "ltp": 120, "quote": 120, "order": 300, "login": 300}
RATE_LIMIT_WAIT_SECONDS = RATE_LIMIT_COOLDOWNS["ltp"]  # legacy import
