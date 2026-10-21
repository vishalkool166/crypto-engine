# Self-host Signal Engine

Choose a public site, a private admin site, or both. You may host the interfaces on any static host and run FastAPI/Redis on any supported server. Cloudflare is an optional example in [Cloudflare setup](CLOUDFLARE.md).

## 1. Choose the interfaces

| Deployment | `.env` settings | Frontend build |
| --- | --- | --- |
| Public only | `PUBLIC_APP_ENABLED=true`, `ADMIN_APP_ENABLED=false` | `npm run build:public` |
| Admin only | `PUBLIC_APP_ENABLED=false`, `ADMIN_APP_ENABLED=true` | `npm run build:admin` |
| Both | Set both to `true`; configure distinct origins | Build each interface |

Set the enabled interface origins exactly, including `https://` in production. Public-only hosting does not require Google credentials. Admin hosting requires Google OAuth, the `ADMIN_EMAILS` allowlist, HTTPS, and a strong session secret. The admin build has a dedicated PWA manifest and service worker.

## 2. Prepare the server

Requirements: Docker Engine with Compose, persistent storage, and outbound access to Redis/exchange/Telegram endpoints as configured. Do not expose the FastAPI or Redis ports directly to the Internet. Keep SQLite, the RAG index, and `.env` on protected persistent storage.

```bash
cp .env.example .env
chmod 600 .env
python scripts/setup_env.py
mkdir -p database
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 signal-engine
```

Before first boot, review `.env`: choose enabled interfaces, set their origins, configure `ORIGIN_PROXY_SECRET`, and leave `ENGINE_ENABLED=false` with `TRADING_MODE=paper`. `setup_env.py` creates missing application secrets without printing them or replacing an existing `.env`.

## 3. Build and host the interface(s)

From `dashboard/`:

```bash
npm ci
npm run check
npm run build:public
npm run build:admin
```

Publish `dist/public`, `dist/admin`, or both. Configure each static host to rewrite client-side routes to `index.html` and provide same-origin proxy routes for `/api/*`, `/auth/*`, `/ws/*`, and `/webhook/*`. The proxy must inject `X-Origin-Verify` from the server-side `ORIGIN_PROXY_SECRET` and forward the original app host in `X-Forwarded-App-Host`. Do not expose these secrets as frontend build variables.

`deploy/Caddyfile.example` demonstrates serving both builds and proxying the required routes. Remove the unused site block if hosting only one interface. Adapt the same routing and trusted headers for Nginx or another reverse proxy. Keep the FastAPI container private behind that proxy.

## 4. Configure Google OAuth (admin only)

1. Create a Google OAuth client of type **Web application**.
2. Add the admin origin as an authorized JavaScript origin.
3. Add `https://<your-admin-host>/auth/callback/google` as an authorized redirect URI.
4. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `ADMIN_EMAILS` in the backend `.env`.
5. Ensure the admin host routes `/auth/*` to FastAPI and matches `ADMIN_APP_ORIGIN` exactly.

Google is the only browser login. Only allowlisted administrator emails can access private routes. Do not add OAuth secrets to client-side variables.

## 5. Configure Telegram

Set `TELEGRAM_TRANSPORT=webhook`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ALLOWED_USER_IDS`, and `WEBHOOK_SECRET` in the backend `.env`. The proxy must deliver `/webhook/telegram` to FastAPI without a login or interactive bot challenge. For public-only hosting, set `TELEGRAM_WEBHOOK_URL` to a reachable HTTPS route on the public host. Follow [Telegram setup](TELEGRAM.md) to register and verify commands.

## 6. Preserve data and verify

Back up `.env`, `database/`, and `database/chroma/` before upgrades. Never replace these with the clean directories from a new source archive. Use `python scripts/backup.py <new-backup-file>` for a consistent SQLite backup. Follow [Operations](OPERATIONS.md) for restore, mode safety, health checks, and rollback.

Verify the selected site(s), a client-side route, Google login if admin is enabled, a live market-data refresh, Telegram `/ping`, and the research assistant when `GROQ_API_KEY` is configured. An enabled engine also requires valid demo credentials and successful account reconciliation.
