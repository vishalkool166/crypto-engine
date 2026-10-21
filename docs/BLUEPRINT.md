# Product and release scope

## Public site

The public site presents the active market snapshot, signal ledger, recorded outcomes, strategy methodology, and service availability. It distinguishes recorded research from verified profitability and contains no account controls.

## Operator site

The admin site uses Google sign-in with an email allowlist. It provides the operator’s signal and paper-trade view, market configuration, Indian-market integration, research tools, service health, Telegram, audit history, and settings. Sensitive actions remain session- and step-up-protected.

## Runtime and deployment

`dashboard/` is the only frontend source and builds public/admin modes for two Cloudflare Pages projects. Scoped Pages Functions proxy API, auth, websocket, and webhook paths to FastAPI. AWS Compose runs one non-root FastAPI container, Redis, and cloudflared. SQLite and `.env` remain on the host and outside source packages.

The canonical app origins live in backend `.env`; Pages project build mode selects its app target. Frontend API and WebSocket requests remain relative to the current origin. A hostname change also requires updating Pages custom-domain bindings and Google’s callback registration.

## Excluded scope

No customer login, plans, payment workflow, billing automation, live trading switch, or fabricated market data. No GitHub Actions are added. No deployment or provider configuration is performed by creating the source ZIP.
