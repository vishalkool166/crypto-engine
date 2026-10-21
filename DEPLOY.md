# Release deployment

This release has one frontend source tree at `dashboard/`, two Cloudflare Pages builds, and the existing FastAPI service on AWS behind Cloudflare Tunnel. Keep the current `database/` volume and its existing SQLite data when replacing source.

## 1. Configure the AWS service

1. Copy `.env.example` to `.env`. Generate distinct secrets with `openssl rand -hex 48` for `SESSION_SECRET` and `ORIGIN_PROXY_SECRET`; create a separate random `WEBHOOK_SECRET`. Keep `.env` private and do not commit it.
2. Set the Google OAuth client ID and secret. Add `https://admin-app.vishalkool.top/auth/callback/google` as an authorized redirect URI and configure the OAuth consent screen for the admin account.
3. Add the Cloudflare Tunnel token, Telegram bot settings, and any provider credentials you will use. For the engine to reconcile and start its paper scheduler, configure the Binance demo credentials. Set `ENGINE_ENABLED=true` and `TRADING_MODE=paper`.
4. Confirm the host directory mounted at `./database` is writable by container UID/GID 10001. Preserve the existing database. Do not use `chmod 777`.
5. Build and start the stack with `docker compose up -d --build`. Check `docker compose ps`, `docker compose logs signal-engine`, and `curl http://127.0.0.1:8000/health/live` on the host. The FastAPI service is exposed only to the Compose network; Cloudflare Tunnel provides the public route.
6. In the Cloudflare Tunnel, route `api.vishalkool.top` to `http://signal-engine:8000` on the Compose network. Do not create a public EC2 port mapping for the API.

## 2. Create the two Cloudflare Pages projects

Connect the Git repository to **two separate Pages projects**. For both projects set the root directory to `dashboard/`, Node.js version to `22`, and production branch to the intended release branch.

| Setting | Public project | Admin project |
| --- | --- | --- |
| Build command | `npm run build:public` | `npm run build:admin` |
| Build output directory | `dist/public` | `dist/admin` |
| Pages Functions source | `dashboard/functions/` | `dashboard/functions/` |
| `APP_TARGET` variable | `public` | `admin` |
| Custom domain | `app.vishalkool.top` | `admin-app.vishalkool.top` |

Set these **server-side Pages variables/secrets** in each project’s Production environment:

- `APP_TARGET`: as shown above.
- `BACKEND_ORIGIN`: `https://api.vishalkool.top`.
- `ORIGIN_PROXY_SECRET`: the same random value as the backend `.env`.

Keep these variables out of `VITE_*`; they are used only by the Pages Functions runtime. Set the same three values in Preview only if preview deployments are intentionally allowed to reach the production API. Prefer leaving previews without the proxy secret.

The `functions/` directory belongs at the Pages project root, not in `dashboard/public/` or `dist/`. `dashboard/public/_routes.json` is copied into each Vite output and scopes Functions to the API, auth, WebSocket, and webhook prefixes. Pages Git integration or Wrangler deployment is required for Functions; dashboard Direct Upload does not deploy Functions.

For a local Wrangler run, copy `dashboard/.dev.vars.example` to `dashboard/.dev.vars`, fill in the shared secret privately, and change `APP_TARGET` to the build you are testing. `.dev.vars` is ignored by Git.

## 3. Verify routing and login

After both projects deploy:

1. Verify the public root and a client-side route such as `/signals` load the SPA.
2. Verify `https://app.vishalkool.top/api/v1/public/status` returns JSON from FastAPI.
3. Verify `https://admin-app.vishalkool.top/auth/session` returns an unauthenticated response, then visit `/auth/google` and complete Google sign-in with `vishalkool166@gmail.com`.
4. From the admin console, check service status and Redis health. If the engine is not running, inspect the reported startup state and `docker compose logs signal-engine`.
5. Confirm Telegram webhook registration and send `/health` from an allowed Telegram user.

## Domain changes

Frontend API and WebSocket URLs are relative to the active Pages hostname, so there is no `VITE_API_URL` or `VITE_WS_URL` to update. For a new hostname, change `PUBLIC_APP_ORIGIN` / `ADMIN_APP_ORIGIN` in the backend `.env`, configure that hostname on the corresponding Pages project, and update the Google OAuth callback if the admin hostname changes. The API origin remains the Tunnel hostname unless you deliberately change the tunnel route and `BACKEND_ORIGIN` Pages variable.

## WebSocket path

The `/ws/*` Pages Function performs an authenticated same-origin WebSocket bridge to FastAPI. It forwards the browser’s `Origin`, session cookie, and Cloudflare client IP and returns a browser-side WebSocket through a `WebSocketPair`. The browser does not connect directly to the backend hostname.

Cloudflare’s documentation confirms that Pages Functions live at the Pages project root and that Workers can open upstream WebSockets with `fetch`: [Pages Functions setup](https://developers.cloudflare.com/pages/functions/get-started/) · [Workers WebSockets](https://developers.cloudflare.com/workers/examples/websockets/).

## Source safety

Never place `.env`, SQLite databases, API tokens, Google secrets, tunnel tokens, or Pages secrets in the repository or ZIP. Keep a verified backup of `database/` before deploying a schema change. This source package does not deploy DNS, Pages settings, tunnel routes, or OAuth configuration for you.
