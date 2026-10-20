# Migration and deployment

## What this archive contains

- crypto-engine/: the editable repository source.
- prebuilt/public/: Pages-ready public build.
- prebuilt/admin/: Pages-ready operator build.
- START_HERE.md: release overview.

Do not copy prebuilt assets into the backend. They are deployment artifacts; dashboard/ is the only frontend source.

Install the pinned requirements in a Python 3.12 virtual environment before running the Python setup/config/backup scripts on a host. Keep the existing deployment running while preparing the migration.

## 1. Preserve the existing installation

Before changing files, copy the current AWS .env and create a database backup. Keep the current deployment available until the replacement passes smoke checks. Never replace the database directory with the archive’s empty directory.

For an online SQLite backup on AWS:

~~~bash
python scripts/backup.py backups/pre-rebuild.db
~~~

If using the previous installation without this script, stop it first and copy the complete database directory, including WAL/SHM files. Verify that the saved database opens and PRAGMA integrity_check reports ok.

## 2. Update the GitHub repository

Use your existing crypto-engine clone. Keep its .git metadata, private .env, and database directory. Replace its tracked source with crypto-engine/ from this archive; remove the retired frontend/, saas/, and .github/workflows/ directories and old dashboard source before copying. Overlaying files alone will leave obsolete tracked files behind.

Do not rewrite commit history. Do not upload node_modules, prebuilt assets, .env, databases, or backups. If .env or database files were previously tracked, remove them from the index without deleting your local copies and rotate exposed credentials.

Review and push using your existing Git workflow:

~~~bash
git status --short
git add -A
git diff --cached --stat
git diff --cached --check
git commit -m "Rebuild public and operator applications"
git push origin main
~~~

Review the actual staged filenames before committing. This archive does not contain Git history or prove the current remote branch state.

Suggested GitHub About description: “Transparent market research and paper-trading operations with a public signal ledger and private Google-authenticated console.” Add the public app URL only after deployment passes. Suggested topics: python, fastapi, react, cloudflare-pages, paper-trading, market-research. Select a repository license explicitly before advertising it as licensed open-source software.

## 3. Private environment on AWS

Preserve the existing provider credentials. Add the new canonical origins and secrets. For a new installation, run:

~~~bash
python scripts/setup_env.py
~~~

Do not run this over an existing .env. The script refuses to overwrite it. Supply the real Google, Binance demo, Telegram, and Tunnel credentials through the private file/provider settings.

Required for production:
- ENV=production
- PUBLIC_APP_ORIGIN=https://app.vishalkool.top
- ADMIN_APP_ORIGIN=https://admin-app.vishalkool.top
- ADMIN_EMAILS=vishalkool166@gmail.com
- SESSION_SECRET and ORIGIN_PROXY_SECRET: independently generated, at least 32 random characters.
- GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.
- TRADING_MODE=paper.
- TUNNEL_TOKEN for the remotely managed Cloudflare Tunnel.
- BINANCE_DEMO_API_KEY and BINANCE_DEMO_SECRET for the paper engine to start scanning/trading.
- TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, WEBHOOK_SECRET; use TELEGRAM_ALLOWED_USER_IDS for groups.
- REDIS_URL=redis://redis:6379/0.
- SIGNAL_ENGINE_DB_PATH=database/signals.db.

For close-position step-up verification, run `python scripts/enroll_totp.py` on a private interactive terminal, enroll the printed secret/URI in your authenticator, and restart the backend. The script refuses to replace an existing secret. Do not post enrollment output in GitHub or chat.

ADMIN_SESSION_HOURS defaults to 12, maximum 24. ENGINE_ENABLED=false permits an API-only diagnostic startup; it does not simulate a running scanner.

Do not retain old public API/WebSocket build URLs. Legacy DOMAIN/FRONTEND_URL values are no longer read as canonical domains. Historical password and JWT values are no longer accepted for web login.

Before starting the non-root application container, make the preserved database directory writable by UID 10001:

~~~bash
sudo chown -R 10001:10001 database
docker compose build
~~~

The Docker target is Python 3.12. Use exactly one worker/replica.

## 4. Cloudflare Pages builds

Create or update two Pages projects pointing at the same GitHub repository and branch. No GitHub Actions are required.

| Setting | Public | Admin |
| --- | --- | --- |
| Root directory | dashboard | dashboard |
| Build command | npm ci && npm run build:public | npm ci && npm run build:admin |
| Output directory | dist/public | dist/admin |
| NODE_VERSION | 22 | 22 |

Remove VITE_API_URL and VITE_WS_URL from both projects. There are no frontend API secrets or backend absolute URLs. Record the actual project names in PUBLIC_PAGES_PROJECT and ADMIN_PAGES_PROJECT in the root .env. The defaults are signal-engine-public and signal-engine-admin.

The prebuilt directories can also be deployed through Pages Direct Upload for this exact release. Each directory is a separate Pages project. Do not upload the whole source ZIP as static assets.

In this routing design the two app hostnames are NOT custom domains attached directly to Pages. The gateway fetches each project’s pages.dev address. This avoids DNS conflicts between Pages and Tunnel.

## 5. Cloudflare Tunnel

Create one remotely managed cloudflared Tunnel and save its token privately as TUNNEL_TOKEN. Configure two published application routes:

| Hostname | Origin service |
| --- | --- |
| app.vishalkool.top | http://signal-engine:8000 |
| admin-app.vishalkool.top | http://signal-engine:8000 |

Cloudflared runs on the same Compose network as the backend. The two proxied DNS records must target this Tunnel. Resolve/remove the previous Pages custom-domain binding during the cutover; do not leave conflicting CNAMEs.

The Worker in the next step must be deployed before public traffic is switched. Without it, the origin rejects API requests because the gateway secret is absent, and no frontend is served by FastAPI.

## 6. Gateway Worker

Generate the non-secret Worker configuration on AWS or another machine with the Python requirements installed:

~~~bash
python scripts/configure.py
~~~

Read deploy/cloudflare/wrangler.json. It contains both route patterns, canonical origins, and actual Pages upstream URLs. It contains no secret.

Deploy deploy/cloudflare/gateway.js as a Cloudflare Worker named signal-engine-gateway. Use either Wrangler or the Cloudflare dashboard:

- Add generated non-secret vars.
- Add ORIGIN_PROXY_SECRET as a Worker secret, matching the private backend value.
- Configure Worker ROUTES for app.vishalkool.top/* and admin-app.vishalkool.top/* in your zone.
- Do not use a Worker Custom Domain for this gateway.
- Disable the workers.dev public endpoint.

Wrangler commands, if using a machine with Node installed:

~~~bash
npm --prefix deploy/cloudflare ci
cd deploy/cloudflare
npx wrangler secret put ORIGIN_PROXY_SECRET
npm run deploy
~~~

The Worker sends static requests to Pages, stripping cookies. For API/OAuth/WebSocket requests it continues to the DNS/Tunnel origin with verified headers. Public-host admin paths are rejected at the edge and backend.

## 7. Google OAuth

Use a Google OAuth Web Application client. Set the authorized redirect URI exactly to:

https://admin-app.vishalkool.top/auth/callback/google

Use the admin origin as the authorized JavaScript origin if configured in the client. Set the corresponding client ID and secret in the backend .env. Never put the Google client secret in Pages build variables. Retain state/nonce verification; do not replace it with a client-only token or email check.

## 8. Start and verify

~~~bash
docker compose up -d
docker compose ps
docker compose logs --tail=100 signal-engine
~~~

Checks before announcing the release:

1. Public domain renders the public build. Admin domain renders the Google login.
2. Your allowlisted Google account succeeds. Another account is denied.
3. Public browser/API responses contain no account balance, private position sizes, credentials, or logs.
4. Admin HTTP and WebSocket requests without a valid session are denied.
5. Public and admin WebSockets connect through the gateway; reconnect/fallback behaves correctly.
6. Admin health shows actual Redis/database state. No missing health field is treated as “disconnected.”
7. Runtime is running only after paper credentials and reconciliation succeed. A missing credential state is not healthy.
8. Telegram webhook URL uses the admin hostname; private commands work only for allowed sender/chat IDs.
9. Public PWA installs. Its service worker does not cache API/account responses. Reinstall an old-origin mobile app if needed.
10. Engine mode is paper and real-money credentials are not active.
11. Back up and restore the SQLite database on a clean test instance.
12. Configure Cloudflare WAF/rate limits and inspect error/denial logs.

External Google, Tunnel, Pages, Telegram, and exchange checks were not executed by the archive’s local test suite.

## 9. Domain change

Change PUBLIC_APP_ORIGIN and ADMIN_APP_ORIGIN in the private .env, then regenerate/deploy the gateway config, restart the backend, update Tunnel/DNS hostnames, and update Google’s exact callback URI. No frontend API URL replacement or source search is needed. Provider bindings still require the provider-side changes.

## 10. Rollback

Keep the previous source/config revision and verified database backup. If acceptance fails, restore the prior Pages/gateway configuration and backend source/config. Do not downgrade the database by overwriting active records. Stop the service before restoring a backup, verify integrity, and reconcile paper positions before restarting the scheduler.

Never use docker compose down -v for an application upgrade; it deletes the Redis volume.
