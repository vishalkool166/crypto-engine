# Architecture, real source boundaries and API contract policy

## Current observed structure

The ZIP holds `crypto-engine-main/` (FastAPI, trade engine, Redis/SQLite, scheduler, trade and research modules) and `crypto-engine-frontend-main/` (editable React/Vite UI). Backend `frontend/` and frontend `frontend/` are generated static assets, not the maintained React sources. No `.git` history, `.env.example` or production state were supplied.

### Runtime and trust boundaries

```text
Browser [untrusted] → HTTPS reverse proxy → FastAPI HTTP endpoints
Browser [untrusted] → authenticated /ws/dashboard → role/tier-scoped data
Google OAuth + dashboard/TOTP identity → sessions → role enforcement (server)
FastAPI service → SQLite (trades, order intents, user/session/signal/audit records)
FastAPI service → Redis (session/quotas/locks; Angel One Lua quota)
APScheduler (25 defined jobs) → market feeds/scanners/monitor/reports
Crypto scanner → signal grading → risk sizing → durable order intent → Binance
                                     ↘ dashboard / Telegram (trade alerts)
Indian scanner → rate-governed SmartAPI → paper signals / dashboard
RAG/ML → optional local packages and external model services
Resend (NEW) ← account/setup/security service ONLY
```

### Code boundaries that MUST remain correct

- `scheduler.py`: 25 `scheduler.add_job` definitions, including monitor every 30 seconds, scan every 15 minutes and Indian five-minute routines. Starting APScheduler in the FastAPI process creates a duplicate-worker risk if topology changes; inventory leader behavior before changing worker count.
- `database.py`: 28 SQLAlchemy model classes and automatic initialization/migration logic; current SQLite schema and state preservation demand staging migration tests.
- `main.py`: login, Google OAuth, session/API key endpoints, authenticated `/ws/dashboard`, Telegram webhook, dynamic SPA fallback and internal tasks.
- `api/routes.py`, `api/trading.py`, `api/indian.py`, `api/engine_health.py`, `saas/admin.py`: multiple roles and sensitive operations; audit *all* handler paths, not only UI menu visibility.
- `trade/`: uncertain broker outcome is not a rejected order. Keep durable journal and explicit reconciliation; don't auto-resubmit.
- `engines/crypto/strategy.py` documented as legacy alternate prototype; no automatic replacement of canonical agent/scorer.
- `engines/indian/quota.py`: live Redis Lua execution must be tested; FakeRedis unit tests do not establish multi-process safety.
- `frontend/src/lib/api.ts`, `frontend/src/lib/endpoints.ts` and frontend hooks form client contract; query cache and live WS must preserve tier isolation.

## API baseline and versioning contract

Full static list of discovered route decorators is in `SOURCE_AUDIT.json` under `backend_routers_and_entrypoints`. It is not a runtime-authoritative OpenAPI dump. Generate a real OpenAPI schema after a controlled app import; compare frontend endpoint types against it.

### Common collection response (proposed)

```json
{
  "items": [],
  "page": {"limit": 25, "next_cursor": null, "total": 0},
  "sort": {"field": "created_at", "direction": "desc"},
  "filters": {}
}
```

This is a **target proposal**, not existing API behavior. Use stable keyset/cursor pagination for highly active append-only tables where appropriate, or stable offset ordering where total/page numbers are essential. Write a compatibility adapter during transition. API always enforces sort allowlists, maximum page size, permission scoping before query, stable tie-breaker (e.g. timestamp + id), and consistent error schema.

### Live state

Live WS events can update counts/active exposure while the user views history. They must not silently reorder historical pages, reset filters or reveal an admin-only payload. Provide timestamps, freshness and disconnected indicators. Poll fallback should be bounded, and route permission checks must happen on each request, not solely when a WebSocket first connects.

### Environment contract

- `.env.example` shows **names/placeholders only**; never use deploy secrets as examples.
- Production `.env`, broker keys/TOTP, Google OAuth secrets, Resend token, sessions, SQLite and Redis volumes stay outside Git.
- Separate `ENV`, `TRADING_MODE`, explicit `SIGNAL_ENGINE_ALLOW_LIVE_TRADING` guard and readiness health; never treat `paper` as purely offline if it calls exchange demo endpoints.
- Source docs currently warn `GET /api/health` is liveness only; add readiness separate from liveness.
- Deployment must define one logical scheduler/leader and outbound IP policy for Angel One where required.

## Trading invariant trace

1. Ingestion uses valid, fresh, closed candles.
2. Canonical scoring/sizing and per-coin budgets decide eligibility.
3. Exchange/account/DB state must be known before new exposure.
4. Durable intent commits **before** exchange submission.
5. Ambiguous acknowledgement halts retries and triggers reconciliation.
6. Filled quantity and remaining open orders/stop protection are separately reconciled.
7. A local `closed` row is never treated as broker proof.
8. Test fixtures and stale cached data cannot be shown as real-money performance.

Change to any invariant requires explicit task, ADR, baseline input/output comparison and testnet evidence. Until then the behavior remains frozen.
