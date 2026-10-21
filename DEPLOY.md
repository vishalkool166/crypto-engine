# Self-host and Cloudflare deployment

This guide deploys the FastAPI service, Redis and Cloudflare Tunnel on one Linux Docker host, then creates two Cloudflare Pages projects from the same repository. Keep the application database on persistent host storage. Pages is the browser edge; the FastAPI service and Redis stay private behind the Tunnel.

For an existing installation, read [docs/UPGRADE_2_1.md](docs/UPGRADE_2_1.md) first. Container reboot behavior is detailed in [docs/SELF_HOSTING.md](docs/SELF_HOSTING.md); execution activation is covered in [docs/EXECUTION_MODES.md](docs/EXECUTION_MODES.md).

## Deployment map

| Component | Example hostname / location | Exposure |
| --- | --- | --- |
| Public Pages | `app.example.com` | Public, read-only browser app |
| Admin Pages | `admin.example.com` | Private operator browser app; Google sign-in required |
| API Tunnel | `api.example.com` | Publicly routed through Cloudflare Tunnel; app-level origin proxy secret required |
| FastAPI | `signal-engine:8000` | Docker network only; no host port published |
| Redis | `redis:6379` | Docker network only |
| SQLite | `./database/signals.db` | Persistent host directory mounted into the app container |

Replace `example.com` with domains in your Cloudflare zone. The public and admin hostnames must be different. The API hostname is a Tunnel route, not a Pages project.

## 1. Prepare the host and preserve existing data

Use a Linux host with Docker Engine and the Compose plugin. Copy the release source to a durable directory, then inspect the Compose file before startup.

If migrating an existing installation, stop the old application before copying its database. Copy the entire `database/` directory and preserve a second backup outside the deployment directory. Never copy a live SQLite database while writes are in progress.

```bash
docker compose down
mkdir -p database
cp -a /path/to/backup/database/. ./database/
```

Check that `database/` is writable by the image's application user (UID/GID 10001). Fix the directory owner for that UID/GID on the host; do not use world-writable permissions.

## 2. Configure the backend environment

Create a private `.env` file:

```bash
cp .env.example .env
chmod 600 .env
openssl rand -hex 48
```

Set these required production values:

| Variable | Value |
| --- | --- |
| `ENV` | `production` |
| `PUBLIC_APP_ORIGIN` | Exact public Pages origin, e.g. `https://app.example.com` |
| `ADMIN_APP_ORIGIN` | Exact admin Pages origin, e.g. `https://admin.example.com` |
| `ADMIN_EMAILS` | Comma-separated Google email allowlist for this private console |
| `SESSION_SECRET` | Unique random value; do not reuse another secret |
| `ORIGIN_PROXY_SECRET` | Unique random value, at least 32 characters; copied to both Pages projects as a secret |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | OAuth web client credentials |
| `TUNNEL_TOKEN` | Remotely managed Cloudflare Tunnel token |
| `WEBHOOK_SECRET` | Separate random secret for optional Telegram webhook mode |
| `SIGNAL_ENGINE_DB_PATH` | Keep `database/signals.db` unless intentionally migrating the database |

The `.env.example` file documents optional provider and integration settings. Leave `ENGINE_ENABLED=false` for the first boot. Leave `TRADING_MODE=paper`. Live keys are optional. Do not enable live until you complete the explicit setup and TOTP transition described in docs/EXECUTION_MODES.md.

### Google OAuth setup

1. In Google Cloud Console, create or select a project and configure the OAuth consent screen for the private operator use case.
2. Create an OAuth client of type **Web application**.
3. Add the admin site origin (for example, `https://admin.example.com`) to authorized JavaScript origins.
4. Add the exact callback `https://admin.example.com/auth/callback/google` to authorized redirect URIs.
5. Put that client ID and secret in the backend `.env`.
6. Put only the intended operator email(s) in `ADMIN_EMAILS`. Google sign-in is limited to verified accounts on this list.

## 3. Create and route the Cloudflare Tunnel

1. In Cloudflare Zero Trust, open **Networks → Tunnels** and create a remotely managed Cloudflared tunnel.
2. Choose the Docker connector instructions and copy the tunnel token into the backend host `.env` as `TUNNEL_TOKEN`.
3. Add a public hostname route with hostname `api.example.com` and service `http://signal-engine:8000`. The tunnel container joins the Compose network and resolves the `signal-engine` service name.
4. Do not open port 8000 on the host firewall or create a public EC2/security-group port mapping for it. The included Compose file only exposes it to the Docker network.
5. Wait for the tunnel to report healthy/connected before testing the API hostname.

The hostname route can create/manage the DNS record in the Cloudflare zone. Verify that `api.example.com` points at the tunnel rather than at the host's public IP. Keep Cloudflare proxying enabled.

## 4. Start the private backend services

From the release directory:

```bash
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 signal-engine
```

Verify the local container health endpoint from the host using an ephemeral diagnostic container on the Compose network if port 8000 is not published, or use the admin/public browser status after Pages is connected. Check `docker compose ps` for healthy Redis and FastAPI containers. The Tunnel starts after FastAPI becomes healthy.

If initialization fails, keep the engine disabled and inspect logs. Do not delete or recreate `database/` to clear an application error.

## 5. Create the two Pages projects

Cloudflare Pages Functions are required for the same-origin API, OAuth, WebSocket and Telegram webhook routes. Use Git integration so the `dashboard/functions/` source is deployed with the site. The Pages project root must be `dashboard/` so `functions/` is at the project root; do not deploy only `dist/` as a static Direct Upload.

Create two Pages projects connected to the same repository and production branch. For both, set:

| Build setting | Value |
| --- | --- |
| Root directory | `dashboard` |
| Build command | Project-specific value in the table below |
| Build output directory | Project-specific value in the table below |
| Node.js version | `22` |

Then configure each project:

| Setting | Public project | Admin project |
| --- | --- | --- |
| Build command | `npm run build:public` | `npm run build:admin` |
| Output directory | `dist/public` | `dist/admin` |
| Custom domain | `app.example.com` | `admin.example.com` |
| Runtime variable `APP_TARGET` | `public` | `admin` |
| Runtime variable `BACKEND_ORIGIN` | `https://api.example.com` | `https://api.example.com` |
| Runtime secret `ORIGIN_PROXY_SECRET` | Same value as backend `.env` | Same value as backend `.env` |

Set `APP_TARGET`, `BACKEND_ORIGIN`, and `ORIGIN_PROXY_SECRET` under each Pages project's **Settings → Variables and Secrets → Production**. `ORIGIN_PROXY_SECRET` must be a secret, not a `VITE_*` build variable. Pages Functions read these values at runtime. Do not set the production proxy secret in Preview unless preview builds are deliberately authorized to reach the production backend.

After the first successful deployment, add the custom domain in that Pages project and follow the DNS validation shown by Cloudflare. Use separate Pages projects; the admin project must have `APP_TARGET=admin` or private API and webhook routes will reject traffic.

Cloudflare references: [Pages Git integration](https://developers.cloudflare.com/pages/configuration/git-integration/), [build configuration](https://developers.cloudflare.com/pages/configuration/build-configuration/), [Functions setup](https://developers.cloudflare.com/pages/functions/get-started/), [Functions routing](https://developers.cloudflare.com/pages/functions/routing/), and [Tunnel published applications](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/).

## 6. Verify domain routing, proxy and sign-in

Run these checks after the three hostnames resolve:

1. Open `https://app.example.com/` and a client-side route such as `/signals`.
2. Open `https://admin.example.com/`; it should show the sign-in flow while unauthenticated.
3. Request `https://app.example.com/api/v1/public/status`; it should return public status JSON through Pages Functions.
4. Request `https://admin.example.com/auth/session`; an unauthenticated response is expected before sign-in.
5. Sign in with an allowlisted Google account and confirm the admin dashboard loads.
6. Confirm the admin status page reports the backend and Redis health correctly.
7. Open **Performance**, **Trades**, **Trade journey**, and **Stored data**. Empty tables are valid on a new database; existing records should be visible after migration.
8. Open **Telegram** and follow [docs/TELEGRAM.md](docs/TELEGRAM.md) to register and test inbound commands.

If a public API request returns 403, check the Pages runtime secret matches the backend `ORIGIN_PROXY_SECRET`. If admin API calls return 404, check the admin hostname is bound to the admin Pages project and `APP_TARGET=admin`.

## 7. First paper-engine start

Only after backups and health checks pass:

1. Create the API key in the Binance Futures Demo environment and configure that demo key pair. Binance's current USDⓈ-M Futures documentation lists `https://demo-fapi.binance.com` as the testnet REST base URL and `wss://demo-fstream.binance.com` as the testnet WebSocket base. The REST value is configurable through `BINANCE_DEMO_BASE_URL` in case Binance changes it or your integration uses another compatible demo endpoint. When upgrading, update an existing `.env` value if it still contains `https://testnet.binancefuture.com`. See [Binance USDⓈ-M Futures General Info](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/general-info).
2. Verify `TRADING_MODE=paper` and that no live exchange credentials are present.
3. Set `ENGINE_ENABLED=true`, then recreate the service with `docker compose up -d --build signal-engine`.
4. Watch `docker compose logs -f signal-engine` through market connection and reconciliation.
5. Confirm the admin status screen reports a healthy engine and inspect the first paper events.

If reconciliation fails, set `ENGINE_ENABLED=false` and restart the service. Review [docs/OPERATIONS.md](docs/OPERATIONS.md) before trying again.

## 8. Upgrade, backup, restore and rollback

Before every source upgrade, stop writes and back up the database:

```bash
docker compose stop signal-engine
python scripts/backup.py ./backups/pre-upgrade-YYYYMMDD-HHMMSS.db
```

Keep the backup outside the source ZIP and deployment directory. Deploy the new source while preserving `database/` and `.env`, then:

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=200 signal-engine
```

If startup or data checks fail, stop the application, restore the verified database backup using [docs/OPERATIONS.md](docs/OPERATIONS.md), then restore the previous source version. Do not restore an old database over a running service. Preserve both the pre-upgrade and failed-upgrade database copies until the rollback is verified.

## Troubleshooting map

| Symptom | First check |
| --- | --- |
| Public data API is 403 | Pages `ORIGIN_PROXY_SECRET`, `APP_TARGET=public`, `BACKEND_ORIGIN`, backend origin settings |
| Admin API is 404 | Admin project custom domain and `APP_TARGET=admin` |
| Google callback error | Exact redirect URI, admin host, client ID/secret, `ADMIN_EMAILS` |
| Admin login loops or disappears | Session secret, HTTPS custom domain, Redis health, backend logs |
| Telegram alerts arrive but commands do not | Admin Pages webhook Function, `ADMIN_APP_ORIGIN`, allowed sender ID, Redis; see Telegram guide |
| Engine is stopped | `ENGINE_ENABLED`, demo credentials, startup/reconciliation error in backend logs |
| Missing historical records | Correct `database/` mount and `SIGNAL_ENGINE_DB_PATH`; never initialize over the old database |

