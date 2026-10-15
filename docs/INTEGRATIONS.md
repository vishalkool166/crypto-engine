# Integrations and external service boundaries

## Angel One SmartAPI


**Last reviewed:** 2026-10-15. **Operational status:** simulated tests only; NOT independently validated against the Angel One production API or Redis server.

Reference: [Angel One official SmartAPI docs](https://smartapi.angelone.in/docs). The API documentation describes per-**client-code** limits; the order API limit is *cumulative* across place, modify and cancel. The published historical endpoint documentation currently lists **3 requests/sec, 150 requests/min, 5,000 requests/hour**. Some older pages show 180/min; 150 is used as the conservative reference. The current place/modify/cancel combined limit is **9 requests/sec** (not 20).

## Local safety budgets (deliberately lower)

| Operation | Minimum gap | Maximum/min | Maximum/hour | Broker response cooldown |
|---|---:|---:|---:|---:|
| Login | 60s | 1 | 15 | 5m |
| Historical candles | 5s | 100 | 3,500 | 10m |
| LTP / quote | 0.2s each | 400 each | 4,000 each | 2m |
| Order submission/modification/cancellation (future integration) | 0.125s shared | 400 shared | 800 shared | 5m |

The **order governor is not yet wired into order entry** because this repository currently uses Angel One for *Indian market data/paper signals*, not actual Indian order placement. All future SmartAPI order methods must call `quota.admit('order')` **without automatically retrying ambiguous order submissions**.

Every SmartAPI request in this existing Indian data/login integration passes through `engines/indian/quota.py` using Redis `TIME` + Lua atomic rate reservations. Redis must be accessible, persistent, private to the app, and **shared between all workers/app instances using the same Angel One client code**. Redis outage fails closed: no network request is sent. Running the same account across unrelated Redis deployments defeats coordination and is unsupported.

- Historical-success responses cached by token + date range + interval; older completed windows have longer TTL. Invalid OHLCV is rejected.
- LTP response cache is only eight seconds, with the scanner's stale LTP cache reduced to 15 seconds.
- API errors `AB1021`, `exceeding access rate`, `rate limit`, or `too many requests` open **only that endpoint's** circuit. A historical-data 403 does not disable healthy LTP.
- `Access denied` **without** rate information is **not** assumed to be a rate limit: it may be an invalid client, missing static IP, or another broker policy.
- No automatic broker-side 403 retries, request storms, or attempts to evade a provider restriction.
- The login path now makes at most one network attempt per invocation; failed logins do not immediately reattempt.
- Manual `/api/indian/refresh` and scheduler jobs share the same rate gate. See admin-only `GET /api/indian/quota` for endpoint cooldowns, budgets, and quota storage health.

## Incident response

1. Check `GET /api/indian/quota` **as admin**. If `backend=unavailable`, restore Redis; no broker calls will be admitted. Do not bypass the quota code.
2. If only `candles` has a broker cooldown, keep paper signals suspended when candle input is unavailable. The app should continue to serve LTP. Cached historical candles may remain available.
3. Avoid repeated manual refreshes and duplicate services using the same Angel One credentials. Never restart in a loop to bypass cooldowns.
4. Verify the static outbound IP is registered if required for your SmartAPI key. Changes to Angel One's order/OAuth/IP policies are outside the rate governor.
5. If the **first historical request** after the cooldown is rejected, capture sanitized timestamps, endpoint, market segment, status code and error code and raise a ticket with Angel One. Do not share authorization tokens, TOTP secrets, full requests with credentials, or client IDs publicly.
6. Reports of broker-side historical 403/AB1021 below published limits exist: [Angel One community thread](https://smartapi.angelone.in/smartapi/forum/topic/5692/getcandledata-rate-limit-continues-at-very-low-request-frequency-backend-telemetry-check-required/1). Local code cannot solve a server-side account restriction.

## Deployment tests still mandatory

- Run the Lua script against **real Redis 7**, including multiple process instances and Redis reconnection/outage cases (offline tests use a FakeRedis emulator).
- Test all supported SmartAPI operations with your own authorized account in sandbox/paper mode, including endpoint-specific 403/429, malformed replies, holidays, rejected credentials, and clock drift.
- Inspect scheduler/worker topology to ensure only one logical job leader; Redis quota admission does **not** prevent duplicated work, only duplicate quota consumption.
- Keep Indian and Binance live order placement disabled until independent execution safety checks are complete.

## Binance USDⓈ-M futures

The read-only metadata connector verified the 18 configured USDT perpetual symbols on 2026-10-14. Exchange tick sizes, lot increments, and minimum notionals are **symbol-specific and changeable**. Runtime entry validation must use fresh exchange metadata; historical test results must state their execution-rule assumptions.

Read-only historical acquisition is implemented in `backtest/research.py`: 4h and 1h futures candles plus actual funding settlements; manifests record SHA-256 checksums. This is not a credentialed trading client. A completed historical snapshot was **not** downloaded in the current environment because the public download hosts cannot be resolved from this runtime.

Trade-order submission is disabled by default and needs testnet reconciliation, timeout and partial-fill drills. See [Operations](OPERATIONS.md).
