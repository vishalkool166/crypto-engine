# Stored data and retention

The application treats its SQLite database as durable operator history. A deployment upgrade must keep the existing `database/` directory and the configured `SIGNAL_ENGINE_DB_PATH`. This release does not delete customer-era or other legacy tables as part of startup.

## Inspecting records

After Google sign-in, open **Admin → Stored data**. The page lists application tables, shows a bounded/paginated sample, supports text search, and exports the visible table as CSV. It is intended for inspecting and exporting records; it does not mutate rows.

The catalog is read from the active SQLite schema, so it also lists tables not anticipated by the UI. Common records include:

| Data group | Examples |
| --- | --- |
| Market and signals | `signals`, candle tables, Binance market snapshots, funding data |
| Trading history | `trades`, `trade_outcomes`, `trade_journey`, portfolio snapshots |
| Research | `backtest_results`, system versions, thesis snapshots, adaptation recommendations and logs |
| Operations | audit logs, signal deliveries and snapshots, circuit-breaker and rollback records |
| Configuration | coin and instrument configuration, pillar weight history |
| Content | `content_posts` and their publication state |
| Legacy account records | historical users, subscriptions, API keys and sessions |
| Private operator auth | operator identities and hashed sessions |

Names depend on the database's actual schema and migration history. An empty table, an unknown table, or an unfamiliar row is still surfaced in the data browser when present.

## Secret handling

The data API is private to an authenticated operator. Column names that look like credentials, tokens, secrets, hashes, passwords, authorization or cookies are masked in the browser and CSV. This is defense in depth: database backups may contain sensitive material even where a UI projection masks it. Keep downloaded CSV files and database backups private.

The browser's search and page size are bounded. For full-fidelity recovery, use a database backup rather than relying on the UI export.

## Backups

Use the SQLite online backup helper to produce a consistent snapshot, including recent WAL writes:

```bash
python scripts/backup.py ./backups/signals-YYYYMMDD-HHMMSS.db
```

The destination must be a new file. The script runs SQLite's integrity check and sets restrictive permissions. Copy verified backups to storage outside the server. Test restores periodically against a separate copy of the database; never test by overwriting the active database.

For an upgrade, stop the `signal-engine` service before taking a deployment-level backup and preserve `.env`, the SQLite file, and any other operator-managed state. Redis is coordination/cache state; SQLite is the durable application record store.
