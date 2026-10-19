# Engineering workflow

`crypto-engine` is the canonical existing Git repository. Preserve its Git history. Keep Python backend modules and AWS Docker/Compose files at the repository root. Put editable React source in `dashboard/`; Cloudflare Pages builds only that folder.

## Changes and tests

1. Create a branch from the verified deployed revision. Never paste a ZIP over `.git`, `.env`, `database/`, Redis volumes or live state.
2. Record changed modules, API contracts and whether any trading or deployment behavior may be affected.
3. Use `bash scripts/verify_local.sh` from repository root. With available npm network access, run `CHECK_FRONTEND=1 bash scripts/verify_local.sh` (Node 22); record skipped tests.
4. If modifying trading code, add deterministic regression inputs/outputs and adverse-order-state tests. Passing API tests alone cannot justify live trading.
5. Before deploying, independently review auth/cookie/origin changes with a real browser and custom Cloudflare domain, verify backups/restoration and document a rollback target.
6. Update `docs/engineering/MASTER_TASK_LEDGER.csv` **and** its JSON counterpart using stable IDs. Mark tasks VERIFIED only with traceable acceptance evidence.
7. Keep GitHub Actions absent, as requested. Cloudflare's Git integration builds the frontend; existing AWS deployment automation must be independently discovered, never replaced blindly.

## Reviews

Review risky changes in small groups: backend safety, database, authentication, API, frontend, deployment. Keep the previous deployed Git SHA and backup references available. Avoid unrelated renames and dependency upgrades during deployment changes.

## Code discipline

Use established formatting and consistent failure handling. Never present mock/demo values as production data. Expose an explicit unavailable state when external services fail. Preserve the original Outfit/Geist typography and color variables. Design for readable hierarchy and functional tables rather than ornamental dashboard cards.
