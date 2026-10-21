# Cloudflare Pages and Tunnel setup

Cloudflare is one supported hosting option. You may instead host the static
builds and reverse proxy on any provider that supports the routes described in
[SELF_HOSTING.md](SELF_HOSTING.md). No preconfigured application hostname is
required.

## 1. Decide which interfaces to publish

Set these in the backend `.env`:

| Choice | `PUBLIC_APP_ENABLED` | `ADMIN_APP_ENABLED` |
| --- | --- | --- |
| Public only | `true` | `false` |
| Private admin only | `false` | `true` |
| Both | `true` | `true` |

For both, configure separate HTTPS origins. Admin access uses Google OAuth and
the configured `ADMIN_EMAILS` allowlist. Public-only deployment does not require
Google credentials. Build each selected interface using the commands in
[SELF_HOSTING.md](SELF_HOSTING.md).

## 2. Prepare a Cloudflare Tunnel (optional)

The Tunnel keeps the FastAPI service private and accepts only outbound
connections from your host. Create a remotely managed Tunnel in Cloudflare Zero
Trust and copy its token into the server `.env` as `TUNNEL_TOKEN`.

Create a public hostname route such as `api.example.com` to
`http://signal-engine:8000`. Do not publish container port 8000 or open it on the
server firewall. Then start the backend with the tunnel overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml ps
docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml logs --tail=100 cloudflared
```

The tunnel starts independently of the API health state. Docker's `restart:
always` reconnects an exited connector and starts it when Docker starts. It does
not repair an unhealthy but still-running process or a persistent provider
outage; inspect connector and server logs. With the optional systemd unit, set
`COMPOSE_FILE=docker-compose.yml:docker-compose.cloudflare.yml` in the unit's
environment before enabling it at boot.

HTTP/2 uses outbound TCP 7844. If your network allows QUIC, set
`TUNNEL_PROTOCOL=auto`. Do not open inbound ports to work around tunnel errors.

## 3. Create Pages project(s)

Create one Pages project for each interface you chose. Connect the repository
and production branch. Set the project root to `dashboard/` so Pages deploys the
included `functions/` routes together with the frontend.

| Build setting | Public interface | Private admin interface |
| --- | --- | --- |
| Build command | `npm run build:public` | `npm run build:admin` |
| Build output directory | `dist/public` | `dist/admin` |
| Pages runtime variable `APP_TARGET` | `public` | `admin` |
| Custom domain | Your chosen public host | Your chosen private host |

If deploying only one interface, create only that project. A direct upload of
`dist/` without Pages Functions does not include API, auth, WebSocket, or
webhook proxying.

## 4. Configure Pages runtime values

In each Pages project, open **Settings → Variables and Secrets → Production**:

| Runtime value | Public project | Admin project |
| --- | --- | --- |
| `BACKEND_ORIGIN` | Tunnel API origin, e.g. `https://api.example.com` | Same Tunnel API origin |
| `ORIGIN_PROXY_SECRET` | Same secret as backend `.env`, marked secret | Same secret as backend `.env`, marked secret |
| `APP_TARGET` | `public` | `admin` |

Only configure the project(s) you actually deploy. `ORIGIN_PROXY_SECRET` is a
server-side secret. Never use a `VITE_` prefix or compile it into the browser.
Do not expose production backend access to untrusted preview deployments.

The Pages Functions forward trusted host and request headers to the backend.
The public project rejects private admin routes; the admin project handles
Google auth and the Telegram webhook. Add only the selected project host(s) to
the corresponding backend origin variables.

## 5. Configure Google OAuth when hosting admin

Skip this for public-only hosting. For admin hosting:

1. Create an OAuth client of type **Web application** in Google Cloud Console.
2. Set the admin origin as an authorized JavaScript origin.
3. Set `https://<your-admin-host>/auth/callback/google` as an authorized redirect
   URI.
4. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `ADMIN_EMAILS` in the
   backend `.env`.
5. Set `ADMIN_APP_ENABLED=true` and `ADMIN_APP_ORIGIN` to the exact HTTPS origin.

## 6. Register and verify Telegram webhook

Set `TELEGRAM_TRANSPORT=webhook`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`,
`TELEGRAM_ALLOWED_USER_IDS`, and `WEBHOOK_SECRET` in the backend `.env`. The
webhook must reach `/webhook/telegram` without an interactive access challenge.
By default it uses the admin origin; you can set `TELEGRAM_WEBHOOK_URL` to a
different reachable HTTPS route if your chosen topology needs that. On service
startup, the app registers the webhook and command menu. See
[TELEGRAM.md](TELEGRAM.md) for the command list and test sequence.

## 7. Verify the deployment

1. Confirm the Tunnel connector reports connected in Cloudflare and in Docker
   logs.
2. Open each deployed interface and a client-side route such as `/signals`.
3. Request `/api/v1/public/status` on the public host if that interface is
   enabled. A public-only deployment intentionally has no private admin routes.
4. If admin is enabled, verify unauthenticated requests show Google sign-in, then
   sign in with an allowlisted account.
5. Test the backend health page, one market-data refresh, a Telegram `/ping`, and
   the private research assistant when `GROQ_API_KEY` is configured.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Pages API requests return `502` | `BACKEND_ORIGIN`, Tunnel route, backend health, and connector logs |
| API returns `403` | Pages secret must match `ORIGIN_PROXY_SECRET` exactly |
| API returns `404` | `APP_TARGET`, selected interface toggle, route path, and Pages Functions deployment |
| OAuth callback fails | Admin origin, exact Google callback URI, client ID/secret, and allowlist |
| Telegram commands fail | Webhook URL, `WEBHOOK_SECRET`, sender allowlist, Redis, and service logs |
| Tunnel stopped after config change | Recreate it with both Compose files and `--force-recreate cloudflared` |

Cloudflare references: [Pages Git integration](https://developers.cloudflare.com/pages/configuration/git-integration/),
[build configuration](https://developers.cloudflare.com/pages/configuration/build-configuration/),
[Pages Functions](https://developers.cloudflare.com/pages/functions/), and
[Tunnel routing](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/).
