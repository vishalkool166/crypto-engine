# Operations and incident response

**Deployment status: NOT APPROVED FOR LIVE CAPITAL.** The repository has not passed Binance testnet integration, database disaster-recovery, or third-party security review. Treat it as a portfolio/research application until verified.

## Startup safeguards and configuration

- Back up `database/signals.db`, its SQLite `-wal`/`-shm` companions (via SQLite backup API for a live DB), and `database/runtime_state.json` **before** upgrading. Preserve `.env` separately in a secrets manager. Never publish credentials.
- The `database/` volume **must** be mounted on durable storage. The exchange order-intent journal is stored in `database/signals.db` in `exchange_order_intents`. Do not run multiple server replicas against independent SQLite copies.
- `TRADING_MODE=paper` is the normal mode; it uses Binance testnet/demo credentials, not an offline simulator. Even demo mode makes requests to an external exchange environment.
- New live exposure is **denied** unless `SIGNAL_ENGINE_ALLOW_LIVE_TRADING=I_UNDERSTAND_REAL_ORDERS` is explicitly set. This is an additional guard, not a safety certification, and it is not recommended to enable live exposure.
- After an authorized, staged upgrade, check `/api/health` returns `{"status":"alive"}`. This is **liveness only**, not Redis/database/exchange readiness.
- For authenticated administrators, `GET /api/system/health` includes `redis_connected` from a backend ping. A missing response, 401/403 or browser network error is *unknown diagnostics*, not a Redis outage. Check Compose `redis` health separately before restarting anything.
- Cloudflare frontend changes and AWS container updates are independent. Do not restart Redis or overwrite `/app/database` as part of dashboard maintenance.
- Scheduled jobs start after the startup reconciliation attempt. For unresolved trades, automatic re-creation of protective orders is intentionally disabled; intervention is required.

## Ambiguous exchange order: incident response

1. **Stop new orders** and do not repeatedly toggle trading mode or delete the database. An acknowledged order may still be open and unfilled.
2. On the exchange, inspect the `client_order_id` (`se_<uuid>`) against the account and symbol, including open orders, filled orders, executions and positions. Record `orderId`, status, filled quantity and timestamps.
3. Verify that stop-loss and take-profit orders reflect the **actual** exposure. For a partially filled entry, manually reconcile **both** the active position and remaining resting order.
4. Verify the local trade row and `exchange_order_intents` row in the SQLite database (read-only):

   ```sh
   python - <<'PY'
   import sqlite3
   db = sqlite3.connect('database/signals.db')
   for row in db.execute('SELECT intent_key, client_order_id, mode, symbol, status, exchange_order_id FROM exchange_order_intents WHERE status != ?', ('finished',)):
       print(row)
   PY
   ```

5. Escalate if exchange status cannot be confirmed. **Do not mark an intent `finished` or delete it simply to restart automated trading.** Only a trained operator may close an incident after separately verifying exchange orders, positions, the DB, and protective stops. A restoration procedure must be exercised in staging before real capital is permitted.

## Failure modes and limitations

- This is **at-most-once submit per durable intent**, not exactly-once execution. The exchange or database can fail after accepting a request. Manual reconciliation remains necessary after ambiguous responses.
- A journal reservation must commit before the exchange POST; any SQLite/journal failure stops the order before submission. An ambiguous response leaves the intent unresolved and blocks new exposure.
- `reconciliation_required` in the `trades` table is an operational stop signal, **not** proof that a position was closed. Never infer live exchange exposure from a local `closed`/`cancelled` state alone.
- Exchange conditional/algo orders have not yet been journaled or validated for idempotent recovery. Existing protective-order recovery remains incomplete and requires testnet drills.
- Telegram alert delivery is best-effort and must not be relied upon as the sole incident-response channel.
- Redis is configured `noeviction` to avoid silent deletion of session/rate-limit records; monitor Redis memory and errors and plan outages.
- SQLite is suitable for a single durable instance. A distributed deployment requires a reviewed transactional database, single-leader scheduling, and a migration plan.

## Testing

From the `crypto-engine` repository root:

```sh
python -m pip install pytest pytest-asyncio fastapi httpx python-dotenv pandas pyotp
python -m compileall -q -x 'frontend/' .
python -m pytest -q tests
```

The tests cover isolated logic. They do **not** establish successful app startup, end-to-end trading behavior, API routing, third-party integrations or deployment readiness.

## Angel One SmartAPI incidents

Read `docs/INTEGRATIONS.md` before changing throttling. Angel One data requests are now admitted by an atomic Redis Lua quota reservation. Redis unavailability **stops** Angel One requests instead of permitting uncontrolled retry storms. If the historical endpoint rejects with 403/AB1021, **only historical candles** enter a ten-minute broker cooldown; LTP remains separate.

As an authenticated administrator, inspect `GET /api/indian/quota` for the quota backend's state and per-operation cooldowns. Verify the configured client code and registered static IP privately, then escalate persistent low-frequency 403 errors directly to Angel One. Do not bypass broker limits or repeatedly restart the service.

An offline test suite verifies these application-level behaviors but **does not validate** Redis Lua execution, live Angel One responses, or a multi-instance deployment. Do not run real order execution from this build.

## Implementation safeguards (read before upgrade)

- New positions are rejected when risk-state database reads fail, when the proposed exposure is below its permitted minimum stake or when Binance symbol `MIN_NOTIONAL` cannot be verified. This can reduce signal **executions**. It prevents silent risk-budget escalation.
- Scanner's 4h circuit breaker now uses the previous two adjacent **closed** 4h bars, requiring freshness within one 4h cycle plus ten minutes. Stale/missing candle data blocks new positions.
- Routine portfolio snapshots preserve existing nonzero circuit-breaker levels. A sticky halt needs an explicitly reviewed **operator reset procedure**; never edit the database solely to force order entry.
- Daily `sl_hit` limits are based on trade records for the current UTC day. Monitor whether Binance-executed stop closures are reliably written to `Trade.close_reason`; do not assume WebSocket event handlers alone provide the full history.
- Research CLI requires all 3 CSVs (4h, 1h and funding) and their checksums in a manifest before a strategy profitability comparison. Research-only changes have **not** been activated in live signals.

## Release control

No trading-enable changes, schema reset, database replacement, or live deployment is authorized by this source handoff. Run migrations against a restored staging copy first. Validate rollbacks, stop orders, incident response, and data reconciliation with an authorized exchange test environment.

## Source-candidate upgrade control (AWS + Cloudflare)

Current verified user-reported topology: Pages serves `app.vishalkool.top`,
FastAPI and Google OAuth are reached through `signal-engine-v5.vishalkool.top`,
with Redis inside Docker Compose. Do not infer the health of API, WebSocket,
Redis, email or exchange services from a successful Pages build.

1. Record the running Git commit/container image, sanitized environment key
   names, Redis persistence configuration, mount paths and open paper positions.
2. Take an application-consistent SQLite backup using the shipped backup
   script and separately capture the Redis persistence backup per its documented
   volume policy. Test restoration **off the production host**.
3. Build this exact candidate against an isolated staging environment, with
   `PAPER_TRADING=true`, disabled email-account flags and no real exchange
   credentials. Check API and deep frontend routes, role boundaries, Google
   redirect/logout, WebSockets, Redis diagnostics and provisioning.
4. Rehearse a rollback to the previous image, config and compatible database
   state. Migrations are additive in the candidate but still require rehearsal.
5. Only after explicit approval deploy backend changes; monitor liveness,
   Redis, auth, scanners, session validity and reconciliation, leaving the
   existing Compose service name and persisted volumes untouched.

Do not migrate the original public hostname to Cloudflare until a separate API
hostname is provisioned, tested and its OAuth callback/CORS/session cookies
are reviewed. Never use `docker compose down -v` during an upgrade.
