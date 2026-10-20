# Runtime architecture

## Two user-facing hostnames

Both hostnames have proxied DNS records pointing to the same Cloudflare Tunnel. A Worker **Route** matches each hostname with a trailing /*. Static requests fetch the correct Cloudflare Pages project. API, OAuth, webhook, and WebSocket requests continue to the Tunnel origin using fetch(request).

This uses the documented Worker Route origin behavior. Use Routes, not Worker Custom Domains. Do not bind these same hostnames directly to Pages; Pages supplies upstream static assets through its project.pages.dev URL.

The engine remains on AWS. The Worker is a routing/security gateway and does not run the strategy.

## Request boundaries

- Public host: GET/HEAD /api/v1/public/* and /ws/public.
- Admin host: /api/v1/admin/*, selected /auth/* routes, /ws/admin, /webhook/telegram, and public read endpoints.
- Origin: no exposed host port. Tunnel reaches signal-engine:8000 on the Docker network.
- Gateway replaces proxy-verification, app-host, and visitor-IP headers. Backend rejects requests without the matching origin secret in production.
- Admin routes require a live hashed server-side session. Mutations also require the exact admin Origin and a session-bound CSRF token.
- Public signal responses are field allowlists. Internal ORM objects and private trade ledgers are not published.
- Google callback verifies the OIDC identity, verified email, configured email allowlist, and persistent Google subject binding. It creates no customer or subscription.
- HTTP errors do not return backend stack traces. Liveness is separate from private dependency readiness.

## Persistent and transient state

SQLite remains database/signals.db, configurable through SIGNAL_ENGINE_DB_PATH. Existing signal/trade/audit records survive source upgrades. Operator identities and hashed sessions are added non-destructively. Redis handles transient cache, locks, command deduplication, and risk coordination.

Exactly one engine process is supported. The service takes an exclusive host-file lock before starting the engine, and Docker runs one Uvicorn worker. Startup fails closed if a duplicate process starts. Missing paper credentials or failed exchange reconciliation leave the scheduler stopped and visible as such in admin health.

## Configuration

PUBLIC_APP_ORIGIN and ADMIN_APP_ORIGIN are the two canonical URL values in the private root .env. The browser derives API/WebSocket URLs from its own origin. scripts/configure.py generates non-secret Worker configuration from these origins and the selected Pages project names.

Changing an origin requires regenerating/deploying the Worker config, updating the Tunnel/DNS hostname, and updating Google’s authorized redirect. A local .env cannot mutate external provider settings itself.

## PWA

Only the public build registers a service worker. It precaches static assets, excludes auth/API/WebSocket/webhook navigation, and explicitly deletes legacy API caches. The admin build registers no service worker. Account information is never placed in localStorage, IndexedDB, or a service-worker API cache.

## Research boundaries

The deterministic signal decision rules are preserved. New traces are persisted with accepted signals, and rejection traces are available privately. Public traces omit the sizing stage and account values. The old research ML/vector modules remain source-only until separately evaluated; they do not automatically promote parameters or enable live trading.

## Provider references

- https://developers.cloudflare.com/workers/configuration/routing/routes/
- https://developers.cloudflare.com/workers/runtime-apis/websockets/
- https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/
