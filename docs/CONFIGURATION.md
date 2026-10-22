# Configuration reference

The canonical key list and safe example values are in [`.env.example`](../.env.example); implementation defaults live in [`config.py`](../config.py) and [`portal_settings.py`](../portal_settings.py). This guide groups related settings, avoiding a second, drifting copy of their full values.

| Group | Keys / source | Deployment guidance |
| --- | --- | --- |
| Interfaces and origins | `PUBLIC_APP_ENABLED`, `ADMIN_APP_ENABLED`, `PUBLIC_APP_ORIGIN`, `ADMIN_APP_ORIGIN` | Configure only the interfaces you actually publish; use separate HTTPS origins when both are enabled. |
| Authentication | `ADMIN_EMAILS`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SESSION_SECRET` | Google OAuth and allowlist are required for an admin deployment. Keep all secrets server-side. |
| Proxy boundary | `ORIGIN_PROXY_SECRET` | Must match the trusted reverse proxy; never expose as a `VITE_*` frontend variable. |
| Engine and storage | `ENGINE_ENABLED`, `TRADING_MODE`, `SIGNAL_ENGINE_DB_PATH`, `REDIS_URL` | Keep the engine off and mode paper until validated. Preserve database/Redis across upgrades. |
| Binance | `BINANCE_DEMO_API_KEY`, `BINANCE_DEMO_SECRET`, `BINANCE_DEMO_BASE_URL`, `BINANCE_API_KEY`, `BINANCE_SECRET` | Demo keys for paper; live keys are optional until an explicitly authorized future live deployment. |
| Live safeguard | `SIGNAL_ENGINE_ALLOW_LIVE_TRADING`, `TOTP_SECRET`, `MODE_SWITCH_RESTART` | Never enable without demo verification and an account-state review; mode switching remains protected. |
| Telegram | `TELEGRAM_TRANSPORT`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ALLOWED_USER_IDS`, `WEBHOOK_SECRET`, `TELEGRAM_WEBHOOK_URL` | Configure only when using bot commands/alerts. |
| AI and integrations | `GROQ_API_KEY`, `GROQ_MODEL`, `FINNHUB_KEY`, `ANGELONE_*`, `LANGCHAIN_*` | Optional and dependent on chosen integrations. |
| Hosting | `TUNNEL_TOKEN`, `TUNNEL_PROTOCOL`, `CLOUDFLARED_IMAGE` | Cloudflare is optional. Start the tunnel only with the documented Compose overlay and a valid token. |
| Research defaults | `CAPITAL`, `SYSTEM_VERSION`, `ADAPTATION_FROZEN` | Not a substitute for live equity reconciliation or research certification. |

## First installation

For a new instance, run `python scripts/setup_env.py` **instead of** manually copying `.env.example` when you want fresh session, proxy and webhook secrets generated. That script refuses to overwrite an existing `.env`. Restrict it with `chmod 600 .env`, then edit provider keys and exact origins. Do not put `.env` into a ZIP, issue report or pull request.

## Existing installation

Retain the server's `.env` and runtime data. Review changed defaults in `.env.example` without replacing production secrets. In 3.4, no additional mandatory keys are introduced. The saved account mode may persist outside `.env`; inspect it in the admin and `database/runtime_state.json` before restarting a trading engine.

## Optional tunnel

A stock `docker compose up -d --build` runs the backend and Redis, without requiring a Cloudflare token. To run Cloudflare Tunnel as well, set `TUNNEL_TOKEN` privately and use the additional overlay file: `docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml up -d --build`. See [Cloudflare](CLOUDFLARE.md).
