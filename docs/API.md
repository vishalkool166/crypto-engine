# HTTP API and access boundaries

This is an operator-oriented route overview, not a generated OpenAPI contract. The exact request/response schema and route availability are defined in `main.py` and `api/`. FastAPI's interactive documentation is disabled (`/docs`, `/redoc`, and `/openapi.json` are not mounted).

## Public projection

| Route family | Purpose |
| --- | --- |
| `GET /api/v1/public/overview` | Published market/research overview |
| `GET /api/v1/public/signals` | Public signal projection |
| `GET /api/v1/public/signals/{signal_id}` | Published signal detail |
| `GET /api/v1/public/status` | Public service status projection |

The public interface must never inherit authenticated admin routes merely because both are hosted on the same server.

## Operator API

| Route family | Purpose |
| --- | --- |
| `/api/v1/admin/overview`, `/api/v1/admin/health` | Authenticated overview and system health |
| `/api/v1/admin/strategy-lab/*` | Registry, controls, experiments, research comparison, candles and performance |
| `/api/v1/admin/execution/mode` | Guarded account-mode status and transition |
| `/api/v1/admin/trades/*` | Trade history, open positions and protected management actions |
| `/api/v1/admin/engine/*` | Decision traces, rejection analysis and strategy diagnostics |
| `/api/v1/admin/assistant*` | Optional AI research interface |

Operator routes require an authenticated administrator; mutating routes also enforce trusted Origin and CSRF checks. An operator API response is not a license for a public page to expose account values.

## Other routes

- `/auth/google`, `/auth/callback/google`, `/auth/session`, `/auth/logout`: browser authentication session flow.
- `POST /webhook/telegram`: verified Telegram inbound command path; intentionally not interactive-login protected.
- `GET /health/live`: process liveness only, not exchange or scan health.

In production, the backend expects the trusted proxy to supply the configured verification header and original application host; see [Deployment](SELF_HOSTING.md). The admin and public site must use their exact configured origins. Rate limits and errors may vary by endpoint.

## Client development

Use the existing `dashboard/src/api.ts` request layer and inspect `api/` for concrete payloads. Include JSON contract regression tests when changing field names. Display missing telemetry or historical fields as unavailable rather than rendering `undefined` strings or fabricating defaults.
