# Operations and safety

Keep the application in paper mode until credentials, reconciliation, alerts, and backups are verified. Existing Cloudflare Tunnel deployments should continue using both Compose files (`docker-compose.yml` and `docker-compose.cloudflare.yml`); the base file alone intentionally excludes the optional tunnel. The engine should run as one container and one Uvicorn worker.

## Routine health checks

```bash
docker compose ps
docker compose logs --tail=100 signal-engine
docker compose exec redis redis-cli ping
```

The operator console's System Health page shows dependency state. The liveness endpoint only confirms that FastAPI responds; it does not confirm scanner, exchange, Telegram, or Redis health. On the Trades page, confirm the Binance mark feed reports live before relying on second-by-second mark P&L.

## Paper and live mode

Paper uses Binance USDⓈ-M demo trading; live mode can submit real orders. Live requires all of the following in the server `.env`:

```dotenv
ENGINE_ENABLED=true
TRADING_MODE=paper
BINANCE_DEMO_API_KEY=your_demo_key
BINANCE_DEMO_SECRET=your_demo_secret
BINANCE_API_KEY=your_live_key
BINANCE_SECRET=your_live_secret
SIGNAL_ENGINE_ALLOW_LIVE_TRADING=I_UNDERSTAND_REAL_ORDERS
TOTP_SECRET=your_base32_authenticator_secret
```

Use a dedicated futures account in one-way position mode. Grant only required permissions; disable withdrawals. Keep keys and the TOTP secret server-side. Generate a new TOTP secret on a trusted machine with the Python requirements installed:

```bash
python -c 'import pyotp; print(pyotp.random_base32())'
```

Add it to an authenticator as a six-digit, 30-second time-based code and keep server time synchronized.

To switch from admin, open the execution-mode control, select the target mode, type the confirmation phrase shown, enter a fresh TOTP code, and confirm. Both directions require an authorized Google session, CSRF protection, rate limits, Redis-backed replay prevention, and account checks. The transition refuses while there are active local trades, unresolved order intents, account positions, or orders. It does not close orders or positions for you.

The selected mode is persisted in `database/runtime_state.json`; ordinary restarts do not reset it. Do not delete this file. Changing `TRADING_MODE` alone does not override an already saved selection. `MODE_SWITCH_RESTART=true` relies on the included Docker restart supervisor; do not use it with an unmanaged Uvicorn process.

## Backups and restores

Back up before every upgrade. The SQLite online backup helper includes committed WAL data and checks the result:

```bash
python scripts/backup.py "backups/signals-$(date +%Y%m%d-%H%M%S).db"
```

Keep backups outside the running server and restrict access. Preserve the complete `database/` directory, `database/chroma/`, `.env`, and `SIGNAL_ENGINE_DB_PATH`. Existing signals, trades, performance, journey snapshots, runtime state, and historical rows are not dropped by an upgrade. Feature pages show the records relevant to each workflow; use `sqlite3 -readonly` on a backup copy to inspect records without changing production data.

For restore, stop the application, verify the backup, restore the database and RAG index, set correct ownership, then restart. Never restore over a running database. Do not use `docker compose down -v` for an application update; it removes the Redis volume.

## Update and rollback

1. Back up `.env`, the database, RAG index, and runtime state.
2. Replace application source while preserving those files and directories.
3. Rebuild with `docker compose up -d --build` and inspect application logs.
4. Deploy the selected frontend builds and verify Google login, market refresh, Telegram `/ping`, and the research assistant.
5. If acceptance fails, restore the previous backend and frontend builds. Keep the same database unless a migration-specific rollback procedure requires otherwise; reconcile account and order state before restarting the engine.

## Security essentials

- Keep API and Redis ports private. Use a reverse proxy or tunnel and same-origin routing.
- Use unique strong session, proxy, webhook, and TOTP secrets; set `.env` permissions to `600`.
- Restrict Binance API keys by IP where supported and never enable withdrawal permission.
- Use an explicit Telegram sender allowlist, particularly for group chats.
- Do not place secrets in frontend variables, logs, source control, screenshots, or support messages.

Test results do not establish trading profitability or guarantee exchange availability. Live orders and real account mode transitions require operator review.
