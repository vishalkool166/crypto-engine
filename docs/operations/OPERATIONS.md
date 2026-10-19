# Operator runbook — engineering handoff

**Use staging and paper mode. This package is not approved for live trading.** Existing backend startup creates recurring jobs, external connectivity and privileged control routes. Multiple application replicas could duplicate tasks. Never scale the backend above 1 scheduler instance without a separately verified single-leader design.

## Fresh machine

1. Clone privately, copy `.env.example` to `backend/.env`, provision secrets from your secret manager, verify `TRADING_MODE=paper`. Do **not** use actual brokerage keys in a developer environment.
2. Start Redis: `docker compose -f infra/compose.dev.yml up -d`.
3. Install Python 3.11 requirements and frontend lockfile dependencies using the root README.
4. Test: `(cd backend && python -m pytest -q)` then `(cd frontend && npm ci && npm run lint && npx tsc -p tsconfig.app.json --noEmit && npm run build)`.
5. Only in a contained staging system, start a single backend instance and test `/api/health`, login, data isolation, scanner shutdown and a full paper-mode restart. Import external keys through deployment secrets, never git.

## Backup / restore

- Preserve existing SQLite WAL and journal state with a transactional `sqlite3.Connection.backup`, not a raw copy during active writes.
- Use `python scripts/backup_sqlite.py --source /path/to/live.db --destination /secure/offsite/db-YYYYMMDD.sqlite` from the same host with volume read permissions. This script fails closed if the destination exists.
- Restore **only with all API/scheduler/execution processes stopped**; verify journal consistency and broker truth before starting. Verify SHA-256 and run `PRAGMA integrity_check`. Redis AOF and other state, `.env` and exchange-side positions require their own protected migration plan.
- Test backup/restore on a disposable staging copy first. Unrelated data/volume cleanup must never run during migration.

## Incidents

- API unavailable: check read-only health/logs, Redis and disk; avoid immediately restarting during ambiguous broker submit state.
- Exchange unresponsive/unknown fills: block new exposure; reconcile positions, orders and durable intent journal before resuming. Do not blindly retry a write request.
- Scheduler duplicate: stop the extra process safely; review any ambiguous orders and journal before restarting.
- Credential compromise: rotate at provider, invalidate sessions and inspect audit events. Never email raw passwords, TOTP or API keys.

## Release boundary

No access was provided to AWS, a real broker/testnet, verified Resend sending domain, or GitHub. Release gates needing those must remain BLOCKED. The deployment commands here are untested against actual production volumes and must not be used as a blind cutover procedure.

## Production-style image build (staging only)

The **root** `Dockerfile` compiles the React source during a multi-stage build. It replaces all old assets under `backend/frontend/` inside the image; never deploy the stale static directory directly. `compose.yaml` hard-enforces `TRADING_MODE=paper`, disables Resend without a reviewed email lifecycle, binds API to loopback, persists SQLite and Redis data in Docker volumes, and runs one Uvicorn worker. It is a candidate staging setup, not an audited production deployment.

```bash
cp .env.example backend/.env
# Set your local non-production secrets in backend/.env
# Requires Docker Compose and internet access to download Docker/npm/PyPI dependencies.
docker compose build
docker compose up -d
docker compose ps
curl -fsS http://127.0.0.1:8000/api/health
```

For an external website, use a separately verified HTTPS reverse proxy and firewall configuration; never publish Redis. `docker compose down -v` destroys volumes. **Never use `-v` when the volumes hold a real order journal.** A Docker health check only shows HTTP readiness, not broker safety.
