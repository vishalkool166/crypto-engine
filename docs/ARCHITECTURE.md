# Architecture

The system has one FastAPI service and one React source tree.

- `dashboard/` builds the public and admin SPAs in Vite modes `public` and `admin`.
- Each SPA is a separate Cloudflare Pages project with its own custom domain and `APP_TARGET` setting.
- Path-scoped Pages Functions forward only `/api/*`, `/auth/*`, `/ws/*`, and `/webhook/*` to the FastAPI service.
- The AWS host runs FastAPI, Redis, and cloudflared in Docker Compose. SQLite persists in the host-mounted `database/` directory.
- The backend accepts application traffic only when it includes the Pages origin-verification secret. Its forwarded app-host check separates public projection routes from operator routes.

The browser uses same-origin relative URLs. Admin sessions are host-only secure cookies on the admin domain; CSRF-protected mutations include the session CSRF token and exact Origin. The Pages Functions preserve browser cookies and OAuth redirects. WebSocket frames are bridged between the same-origin client connection and FastAPI.

## Public and private data

`api/portal.py` builds explicit public response projections. Public routes expose research records, methodology, outcomes, and limited service status. They do not serialize private trading accounts, credential values, private position sizing, or internal logs. Admin routes require an operator session.

The service runs paper mode only. The scheduler starts after demo-exchange authentication and startup reconciliation succeed. Redis supports coordination, step-up verification, rate controls, and Telegram deduplication. The application does not start a customer billing or subscription system.

## Domain configuration

The browser uses relative API and WebSocket paths, so there are no API host values compiled into frontend bundles. Backend `PUBLIC_APP_ORIGIN` and `ADMIN_APP_ORIGIN` configure OAuth, cookies, and host authorization. Each Pages project receives `BACKEND_ORIGIN`, `ORIGIN_PROXY_SECRET`, and `APP_TARGET` as runtime settings. A domain change also requires a Pages custom-domain binding and Google callback update; editing a local `.env` cannot change Cloudflare account configuration.
