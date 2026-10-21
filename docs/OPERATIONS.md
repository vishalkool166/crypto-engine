# Operations

Use [DEPLOY.md](../DEPLOY.md) for release configuration and deployment. This page records recurring operating tasks.

## Routine checks

```bash
docker compose ps
docker compose logs --tail=100 signal-engine
docker compose exec redis redis-cli ping
```

The liveness endpoint only confirms that FastAPI responds. It does not report whether the scanner, exchange session, Telegram bot, or Redis is healthy. Use the operator console’s System Health page for dependency status.

## Backups

Run the online SQLite backup before deployment or migration:

```bash
python scripts/backup.py backups/signals-$(date +%F).db
```

Copy the backup to protected storage and periodically verify `PRAGMA integrity_check` on a separate test database. The database folder is bind-mounted; preserve its contents and correct UID 10001 ownership when updating the container.

Never use `docker compose down -v` during an application update. It removes the Redis volume.

## Engine startup

Keep one application container and one Uvicorn worker. `ENGINE_ENABLED=false` is for API diagnostics and intentionally prevents the engine from starting. With the engine enabled, the service first connects to the market stream, authenticates to the configured demo exchange, reconciles positions and outstanding order intents, then starts scheduled scans. A reconciliation failure keeps the scheduler stopped and reports a failed state.

The engine runs in paper mode only. Do not use production exchange credentials. Review service logs and actual dependency health after every restart.

## Source release and rollback

Preserve `.env`, `database/`, and backups outside source replacement. Keep the previous Pages deployment available until the new public and admin sites pass acceptance checks. To roll back, restore the prior Pages deployments and backend source revision, then reconcile the existing paper account state before restarting the scheduler.

Never restore a database backup over a running process. Stop the service first, verify the backup, restore it, and check ownership before restart.
