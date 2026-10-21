# Upgrade to 2.1

This upgrade changes the frontend, inbound Telegram transport, container restart
policy, and execution-mode control. Existing SQLite records are retained.

## 1. Back up before replacing code

Stop the stack, copy the complete `database/` directory and `.env` to a private
backup location, then replace application files. Keep the current `database/`
directory and completed `.env`; do not replace them with the ZIP's empty examples.
The schema migration adds `trades.execution_mode` without deleting records.
Existing trades are labelled `legacy`, because their environment cannot be
established from old rows alone. New trades store `paper` or `live` explicitly.

## 2. Update the server environment

Keep `TRADING_MODE=paper` for the first upgrade. Add:

```dotenv
TELEGRAM_TRANSPORT=polling
TUNNEL_PROTOCOL=http2
CLOUDFLARED_IMAGE=cloudflare/cloudflared:2026.10.2
```

Set `ENGINE_ENABLED=true` only when your exchange and database are ready for
execution. Telegram polling still starts when the engine is disabled.

`MODE_SWITCH_RESTART=true` is supplied by Compose, overriding the `.env`
default. Outside Compose, configure a process supervisor before enabling it.

## 3. Recreate containers, rather than merely restarting old ones

From the repository root:

```bash
docker compose config --quiet
docker compose pull redis cloudflared
docker compose up -d --build --force-recreate --remove-orphans
docker compose ps
docker compose logs --tail=100 cloudflared signal-engine
```

`restart` alone does not apply modified environment variables, image references,
or restart policies. Do not run `docker compose down -v`; the volume holds Redis
coordination and replay-protection state.

The tunnel is now independent of API readiness. It starts even if the application
needs attention. It uses HTTP/2 by default, avoiding a dependency on outbound UDP.
Both services use `restart: always`. The Docker daemon must also start at boot.
See [Self hosting](SELF_HOSTING.md).

## 4. Redeploy both Pages projects

Use Node 22 LTS or later supported by Vite. Run `npm ci` in `dashboard/` and build:

- Public: `npm run build:public`, output `dist/public`, `APP_TARGET=public`.
- Admin: `npm run build:admin`, output `dist/admin`, `APP_TARGET=admin`.

Keep the Pages project root at `dashboard/` so its `functions/` directory is
deployed. Keep the existing `BACKEND_ORIGIN` and `ORIGIN_PROXY_SECRET` server-side
secrets. Redeploy both projects after updating dependencies and the lockfile.

## 5. Verify the actual installation

1. Open public and admin on a phone. Switch both themes and reload.
2. Sign in to admin with the allowlisted Google account.
3. Inspect Performance, Trades & journey, Stored data, and System health.
4. Open Telegram operations. The transport should say `polling`, with a connected
   command service. Send `/start`, `/ping`, `/help`, then `/health` to the bot.
5. If a command is ignored, inspect Latest command result. `chat_mismatch` means
   the configured chat differs; `sender_not_allowed` means the sender ID differs.
6. Configure and test your authenticator before attempting any execution changes.
7. Follow [Execution modes](EXECUTION_MODES.md) if you choose to enable live trading.

The source has automated checks. This environment cannot validate your actual
Docker host, Cloudflare routes, Telegram token, Google OAuth configuration, or
Binance account permissions. Those checks must succeed on your installation.
