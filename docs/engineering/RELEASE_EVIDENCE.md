# v1.0.0-rc1 verification evidence — 2026-10-19

**Release claim:** source-level engineering candidate only. Not a certified completed R5 deployment or live-trading release. No repository remote, EC2 instance, Cloudflare project, provider inbox, Redis production volume or exchange account was modified.

## Verified locally

- `bash scripts/verify_local.sh`: **161 tests passed, 1 skipped** (auth dependencies unavailable in isolated Python 3.13), Python source compilation, upstream AWS runtime SHA guard, source hygiene heuristic, task ledger invariants.
- Python 3.11 grammar parse verified for source files; actual Python 3.11 runtime and package installation not tested.
- 90 TypeScript/TSX files parsed with **0 syntactic diagnostics**, not a substitute for type-checking.
- Cloudflare deploy environment check: missing required HTTPS/WSS origins rejected; compatible matching origins accepted.
- Synthetic SQL tests verify full-user search before pagination, proper audit search/action/success filters before counting, wildcard escaping, bounds and stable page order.
- SQLite backup/restore tests exercise checksums, integrity checks and refusal to overwrite active/previous restore destinations, using isolated synthetic data only.
- Cache control changed to `no-store, private` for `/api/` and `/auth/` responses; cookie-request Origin guard is opt-in and unit-tested (not exercised against browsers).
- Existing AWS root-level `Dockerfile`, `docker-compose.yml`, `config.py`, `scheduler.py`, and `auth.py` remain byte-identical to supplied source; no scheduler names, modes or broker logic changed. `main.py` adds only optional redirect/caching/origin guard functionality.
- No GitHub Actions workflows, npm dependencies, `.env`, `.sqlite`/`.db`, compiled build outputs or local Git metadata in the shipped source ZIP. Older AWS `frontend/` static fallback remains for compatibility.
- Task ledger: **141 tasks: 2 verified, 43 implemented but not fully verified, 96 planned**. Statuses are acceptance-based, not completion percentages.

## Blockers before v1.0.0 certification

1. Connect existing Git repo while preserving `.git` and inspect AWS automatic update behavior; no production-branch push until confirmed.
2. On Python 3.11 with all dependencies: fresh `pip install`, complete suite without skips, Docker build, startup/shutdown, actual Redis + SQLite transaction behavior.
3. With npm registry reachable: `cd dashboard && npm ci && npm run lint && npx tsc -b && npm run build`; inspect assets and Cloudflare build logs.
4. On a custom Pages subdomain and staging AWS backend: Google OAuth, admin login, TOTP, cookies, CORS, WebSocket, logout, session revocation, user/admin route authorization, pagination, mobile and keyboard usability. Enable Origin guard only after compatibility tests.
5. Resend provider integration remains **disabled**: account verification, password recovery, abuse limits, token entropy/expiry/single use, account enumeration defense and session revocation must be implemented and tested before activation. Never send signals/trades/reports/marketing via email.
6. Trading paper/demo regression and broker failure tests, single scheduler instance, DB and Redis real-state backups/restore, rollback rehearsal and release sign-off remain pending. Nothing here authorizes live trading.

## Known constraints

The isolated runner cannot contact the npm registry (DNS EAI_AGAIN), has no Docker daemon and lacks part of the Python auth dependency stack. A pre-existing test module is skipped on these constraints. The user has not provided access to AWS, Cloudflare, or the GitHub repository; no tool may claim those systems were modified or verified.

See `RELEASE_GATES_V1.json` for machine-readable release gate statuses and `docs/operations/AWS_CLOUDFLARE_ROLLOUT.md` for the safe merge instructions.
