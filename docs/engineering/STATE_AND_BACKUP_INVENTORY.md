# State and backup inventory

**Scope:** local source-path inventory for the Signal Engine candidate. This is not a manifest of the running AWS instance; live mount points, Redis persistence, retention, offsite copies and actual database contents have not been inspected.

| State | Source path / owner | Durability and handling |
|---|---|---|
| Main SQLite application data, including trades, sessions, audit and user records | `SIGNAL_ENGINE_DATABASE_PATH`; default `database/signals.db`; SQLAlchemy models in `database.py` | Persistent source-of-truth data. Back up SQLite consistently, including WAL state; verify restore on a separate copy before migration. Never replace the live file with a development database. |
| Exchange order-intent journal | Same durable `database/signals.db` path; `trade/order_journal.py` | Reservation must be committed before broker submission; unresolved intents must be reconciled. Backup with the application DB so execution evidence is not split across files. |
| Runtime risk and health state | `database/runtime_state.json`; legacy root `runtime_state.json` is moved on startup if present | Local file-based state. Treat recovery markers and breakers as operational state; include in a coordinated backup and verify restoration policy before restart. |
| Redis | External service configured by runtime environment; accessed through `redis_client.py` | Holds coordination, rate governors, caches and some ephemeral session/market state. Local source does not establish live persistence, eviction policy, or backup status. Do not treat Redis as the sole durable order journal. |
| Chroma/RAG index | `database/chroma` via `rag/vectorstore.py` | Rebuildable derived index, may contain imported documents. Inventory source/PII and rebuild procedure before deciding whether to back up or prune. |
| Market and research data | Application data pipeline, backtest/research modules and mounted paths determined by deployment configuration | Dataset provenance and persistence are not established from source alone. Keep immutable research inputs/manifests separate from runtime writes; no live dataset was copied into this candidate. |
| Frontend/build output and caches | `dashboard/dist`, `dashboard/node_modules`, Python caches | Reproducible derived artifacts. Excluded from source release archives; regenerate from lockfiles and local build commands. |

## Backup and restore rules

1. Identify the live database, runtime-state file, Redis persistence settings and mounted volumes from the deployment before any operation.
2. Stop or quiesce writers for a coordinated application/intent-journal backup, or use SQLite's online backup mechanism; do not copy only the main SQLite file while WAL writes are active.
3. Keep encrypted off-host backups and secrets/keys separately. Never commit live state to the repository.
4. Restore to a new path, validate SQLite integrity and schema, and reconcile unresolved order intents against the broker before resuming new exposure.
5. Record backup age, source revision, checksum, restore result and operator. Retention and cadence remain deployment decisions and must be confirmed against the running system.

## Evidence boundary

This inventory was derived from source paths and code references. It does not prove current AWS mounts, Redis durability, backup freshness, offsite retention, or a successful production restore. Those remain explicit operational gates.
