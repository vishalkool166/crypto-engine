## Current local audit — 2026-10-20 (mode-transition fix)

This source candidate is local only; this is not evidence about the deployed AWS revision.

- `PATH=/tmp/signal-engine-testenv/bin:$PATH CHECK_FRONTEND=1 bash scripts/verify_local.sh`: **262 Python tests passed**. Monorepo contract, source hygiene heuristic, ledger integrity, OpenAPI, source security inventory, schema inventory, SBOM, Indian market scope and S0 checksum checks passed.
- OpenAPI: 125 HTTP operations. Source inventory: 130 HTTP/WS route operations. SQLAlchemy schema: 31 tables. SBOM: 745 dependency components.
- Frontend lint, TypeScript project check and Vite production build passed on Node 24.19.0 / npm 11.9.0. Known mixed import warning for `authStore.ts` and runner `http-proxy` npm config warning remain.
- Both trading-mode endpoints now share an ordered transition that closes the exchange client before persisting or applying the new process mode. Focused safety tests verify close failure leaves mode unchanged and persistence untouched. Offline tests also exercise limit-entry FILLED, confirmed CANCELED, and partial/ambiguous fill branches that require reconciliation. Circuit-level tests cover tiers 0–6, sticky halt preservation, fail-closed daily-stop data, and risk reduction in adaptive sizing. Golden tests freeze scoring boundaries and verify unfinished newest market candles are excluded; existing coverage checks per-coin targets, UTC session boundaries, and rejection cases. Scanner start and monitor stop now require TOTP and emit audit entries for successful and denied requests. Manual closes use the durable active trade record as the sole coin/direction source, reject inactive rows, and audit execution outcomes. This does not complete the broader execution-endpoint authorization task, account-level equity integration, operator reset workflow, or protective-order testnet coverage.
- Ledger: 146 tasks; **4 VERIFIED, 67 IMPLEMENTED_UNVERIFIED, 75 PLANNED**. No task was promoted to VERIFIED.
- No staging/browser, AWS, Cloudflare, OAuth/provider, Redis, testnet, or live exchange checks were performed. Signal quality remains **NOT EVALUATED**. No deployment or real-money execution occurred.

# Release evidence (read before deploy)

## Current local audit — 2026-10-20 (Phases 04–06 batch)

This source candidate remains local only and is not evidence about any deployed revision.

- Implemented a durable new-exposure halt with fail-closed malformed/unavailable-state behavior. The operator reset route requires administrator access, TOTP, an active halt, explicit confirmation, fresh empty exchange positions, no unresolved local trade states and no unresolved order intents. Reduce-only close orders remain allowed during a halt.
- Versioned and validated the SQLite order journal. Existing valid intent tables are backfilled with schema metadata without rewriting intent rows; unknown future versions are rejected. Added release-audit enforcement that configured trading mode is `paper`.
- Focused control, reconciliation, integration-boundary, RAG, ML and release regressions: **98 passed**. Final `scripts/verify_local.sh`: **288 Python tests passed**; monorepo contract, source hygiene, ledger, OpenAPI (126 HTTP operations), source API inventory (131 route operations), ORM schema (31 tables), SBOM (745 components), Indian paper/data scope (11 files) and S0 hashes (15) passed. Frontend clean install, lint, TypeScript project check and production build passed on Node 24.19/npm 11.9.
- Phase 04 ledger now has 20 tasks: **19 IMPLEMENTED_UNVERIFIED, 1 PLANNED, 0 VERIFIED**. Local tests do not promote operational or exchange-dependent work to verified.
- Phase 05 ledger now has 9 tasks: **6 IMPLEMENTED_UNVERIFIED, 3 PLANNED, 0 VERIFIED**. Phase 06 has 12 tasks: **9 IMPLEMENTED_UNVERIFIED, 3 PLANNED, 0 VERIFIED**.
- New local work adds replay-protected Telegram mutations, durable audit-before-mutation behavior, startup reconciliation halts for unknown/mismatched positions, Indian admin/data-failure coverage, bounded/untrusted RAG handling, explicit simulated-P&L provenance, chronological ML holdout safeguards, and fail-closed exchange metadata handling. Focused regression suite: **98 passed**.
- Overall ledger: 149 tasks; **4 VERIFIED, 88 IMPLEMENTED_UNVERIFIED, 57 PLANNED**. No task was promoted to VERIFIED in this batch.
- Remaining Phase 04–06 planned items require protective-order/testnet drills; real Redis; authorized broker/IP and cross-market checks; reversible DB migrations and retention design; and complete immutable historical data for 18-symbol out-of-sample research. No staging, AWS, Cloudflare, Redis service, provider, broker, or live exchange access occurred.

## Continued local audit — 2026-10-20

- Latest `PATH=/tmp/signal-engine-testenv/bin:$PATH CHECK_FRONTEND=1 bash scripts/verify_local.sh`: **229 Python tests passed**; frontend `npm ci`, ESLint, `tsc -b`, and Vite production build passed on Node 24.19.0 / npm 11.9.0.
- Added deterministic integrity gates: OpenAPI route/schema parity (125 HTTP operations), source API authorization inventory (130 operations), database ORM inventory (31 tables), CycloneDX SBOM (745 Python/npm dependency components), Indian SmartAPI direct-order-call scan (11 source files), and 15-file S0 source checksum.
- Added `/api/ready` as a sanitized DB/Redis readiness probe, separate from `/api/health` liveness; local tests cover dependency failure and HTTP 503 behavior. Live dependency checks remain unverified.
- Added process-level SQLite order-intent reservation test. Initial run found `database is locked` during concurrent per-process WAL initialization; bounded retry is now in `trade/order_journal.py` and the separate-process concurrency test passes. This does not replace broker/testnet reconciliation.
- Added IST market/ORB boundary tests. Weekday/weekend clock windows are tested; exchange holidays and special sessions are not modeled or verified.
- Added `STATE_AND_BACKUP_INVENTORY.md`, `DATABASE_SCHEMA_INVENTORY.md`, `INDIAN_MARKET_SCOPE.md`, `SIGNAL_QUALITY_STATUS.md`, and a generated `SBOM.cdx.json`. The schema is source metadata; AWS data stores/mounts remain unknown. Signal quality remains **NOT EVALUATED** because approved immutable research data and saved holdout results are absent.
- Ledger: 141 tasks; **4 VERIFIED, 61 IMPLEMENTED_UNVERIFIED, 76 PLANNED**. New source-only artifacts did not close any staging or operational gate.
- No Git remote, AWS/Cloudflare deployment, OAuth/Resend provider, live Redis, broker/testnet, or live exchange access was used. Paper mode remains the default; no strategy parameters were changed.

## Previous local audit checkpoint — 2026-10-20

This audit is for the local source candidate only; it does not describe the deployed AWS revision.

- `PATH=/tmp/signal-engine-testenv/bin:$PATH CHECK_FRONTEND=1 bash scripts/verify_local.sh`: **218 Python tests passed**. Python compile, monorepo protected-runtime hash guard, source hygiene heuristic, ledger integrity, API schema check, API authorization inventory, and strategy S0 hash check passed.
- OpenAPI check: **124 HTTP operations**, unique operation IDs, route/schema parity and registered dashboard WebSocket. Source inventory: **129 route operations**, each classified with a guard or documented public reason.
- Personal API-key behavior is covered by isolated SQLite tests: hashed storage, new-key 90-day expiry, safe-method-only scope, no admin inheritance, expired-key rejection including SQLite naive datetimes, and owner-scoped revocation. Upstream `auth.py` remains byte-identical to the supplied baseline.
- Added `PHASE_03_THREAT_MODEL.md`; cookie Origin guard remains opt-in. OAuth state/callback adversarial tests, live HTTP/WebSocket authorization matrix, custom-domain browser checks, provider delivery and tenant isolation remain staging gates.
- Frontend clean install, ESLint, TypeScript project check and Vite build passed on Node 24.19.0 / npm 11.9.0. The build reports the known mixed static/dynamic `authStore.ts` chunk warning. npm also reports the environment's `http-proxy` config warning.
- Ledger: 141 tasks; **4 VERIFIED, 54 IMPLEMENTED_UNVERIFIED, 83 PLANNED**. No task was marked VERIFIED by this local-only batch.
- No AWS, Cloudflare, Google OAuth, Resend, Redis production, Git remote, exchange testnet or production integration was accessed. No live order or deployment was performed.

## Current workspace audit — 2026-10-19

This audit inspected `Signal-Engine-Phases-01-09-Engineering-Candidate.zip` locally. It is not evidence of the deployed AWS revision. The source-level assessment is in [`INITIAL_ENGINEERING_ASSESSMENT.md`](INITIAL_ENGINEERING_ASSESSMENT.md).

- `python -m pytest -q -rs --disable-warnings`: **208 passed** in an isolated Python 3.12.14 environment, including HTTP-method safety regression checks for state-changing endpoints. The full Python 3.11 target runtime was unavailable and remains unverified.
- Python compilation, monorepo/AWS runtime static contract, source hygiene heuristic, task-ledger validation, and the 15-file S0 hash check passed.
- Frontend: lockfile reconciled with `package.json`; clean `npm ci` passed on Node 24.19.0 / npm 11.9.0. `npm run lint`, `npx tsc -b`, and `npm run build` passed. Lint is warning-free. Route-level lazy loading reduced the largest entry bundle to 230.85 kB raw / 70.37 kB gzip. Vite still reports a mixed static/dynamic import warning for `authStore.ts`.
- Session logout, market scan, and backtest launch routes now require POST; dashboard calls use POST and regression checks guard these paths. This is a targeted fix, not a complete API method/permission inventory.
- The build ran in local mode. The Cloudflare Pages HTTPS/WSS variable check was not exercised with Pages-style environment variables. No browser E2E or visual/mobile audit was run.
- Updated ledger: 141 tasks; 4 `VERIFIED`, 49 `IMPLEMENTED_UNVERIFIED`, 88 `PLANNED`.
- Docker, staging, Redis, Google OAuth, Resend delivery, AWS, Cloudflare, exchange testnet and production were not accessed.
- No remote Git or live trading operation was performed.

Historical test counts below belong to their named earlier workspace runs and must not be presented as results from this current audit.

## Phase 01–02 offline candidate — 2026-10-19

- **173 passed, 1 skipped** via `python -m pytest -q --disable-warnings`.
- Monorepo deployment guard passed via `python scripts/check_monorepo_contract.py`.
- AWS root deployment config and engine source (`Dockerfile`, `docker-compose.yml`, `config.py`, `scheduler.py`, `auth.py`, `trade/monitor.py`) byte-identical to source baseline.
- Removed obsolete AWS HTML asset server and SPA fallback from `main.py`; `/`, `/login`, `/login.html` now use server-configured Cloudflare redirects. Removed `frontend/` and invalid Pages `_redirects` rule from **candidate only**.
- **NOT verified:** running FastAPI startup under full Docker, Google auth end-to-end on updated backend, Pages deep links, live Redis/SaaS, AWS production deploy, brokerage.

The historical Phase 01–02 audit is preserved in the earlier source release, while the latest evidence for Phases 03–04 appears below.

## Previous v1.0.0-rc1 local candidate

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

See `MASTER_TASK_LEDGER.csv` for current task status and `docs/operations/AWS_CLOUDFLARE_ROLLOUT.md` for the safe merge instructions.

---

# Engineering evidence — Phases 03 and 04

## Phase 03: Redis diagnostics

**Confirmed source defect:** `main.py` defines a lightweight `/api/health` route before `api/routes.py` mounts its own detailed `/health` route at the same resulting URL. The frontend expected `redis_connected` from the lightweight response and converted a missing field to `false`. Its "Redis disconnected" warning therefore did not establish a Redis connection failure.

**Source changes:**
- Docker liveness remains at `GET /api/health` with `{"status":"alive"}`; Compose files are unchanged.
- Detailed diagnostics move to `GET /api/system/health`, guarded by `require_admin_access` **before** cached data can be returned.
- The dashboard requests the new endpoint only for administrators, shows **Unknown** if `redis_connected` is missing, and distinguishes an unavailable diagnostics request from a confirmed failure. System alerts now require an explicit `false` from the probe.
- Actual Redis connectivity is probed by the backend. Redis is **not** contacted directly by browsers or Cloudflare.

**External verification still required:** Start the modified API in a staging Compose environment, test authorized and unauthorized HTTP responses, deliberately disconnect/reconnect Redis in staging, and verify the System page updates without exposing information to standard users. Real Redis Lua quota governance remains a separate release gate.

## Phase 04: SaaS provisioning and plan truth

**Confirmed source defects:** The React Pricing and Profile pages hard-coded capabilities different from `config.TIER_FEATURES`. The frontend advertised an eight-hour Free signal delay while the engine configured 30 minutes. It also advertised AI, content, and billing features without verifying deployment or entitlement support.

**Source changes:**
- `GET /api/pricing` is the catalogue used by Pricing and Profile. Tier comparison data are generated from `TIER_FEATURES`; FAQ avoids unimplemented cancellation or self-service billing claims.
- Existing Google accounts now require a matching provider identity and active account status. A legacy user missing a Subscription record receives one using the user's existing tier; existing nonmissing subscriptions are preserved.
- New identities are normalized to lowercase emails; the Google OAuth callback requires a verified Google email and subject identifier.
- Unknown tier changes are refused. Session creation fails explicitly if its database operation fails instead of returning a fabricated unpersisted session ID.
- An independent email/password account and Resend verification are **not** yet operational. Existing identity providers are not silently linked.

**External verification still required:** Test OAuth with existing real Google accounts, SQL migrations/data consistency, session revocation, tier enforcement across every route, and UI Pricing/Profile in a browser against the changed backend. Billing remains disabled. No real-money trading permission is granted by tiers.

## Local evidence and limitations

- `python -m pytest -q`: **181 passed, 1 skipped** on the developer's isolated runner.
- `python scripts/check_monorepo_contract.py`: passed static runtime constraints.
- `python scripts/check_task_ledger.py`: passed task identity and dependency validation.
- 90 TypeScript/TSX files parsed without syntax diagnostics using installed TypeScript's `transpileModule`. This is **not** type-checking or a Vite build.
- Offline `npm ci` could not proceed because npm cache lacks `zustand@4.5.7` and other downloaded dependencies. No UI/browser production build was certified in this environment.
- AWS EC2, live Redis, Cloudflare Pages, and GitHub have **not** been modified by this release. This package is a source candidate only.

**Safety:** The Dockerfile, Docker Compose file, scheduler, configuration, original authentication module, and trading strategies were not modified in Phases 03–04. `main.py` was changed only in Google identity validation; `api/routes.py` in diagnostic routing and authorization; SaaS provisioning files changed independently. Always test a fresh image and preserve production SQLite/Redis state before deployment.

## Phase 05 and Phase 06 candidate — 2026-10-19

- Branch/package base: cumulative **Phases 01–04** ZIP; this is not a snapshot of the live AWS checkout.
- Email-account service: `saas/email_accounts.py` (new isolated tables, hashed 20-minute one-use tokens, scrypt password digests, SQLite-persisted attempt throttles, no Google identity linking, no email-based admin elevation).
- Account endpoints: `saas/email_routes.py`; require **both** `EMAIL_ACCOUNTS_ENABLED=true` and `SECURITY_EMAIL_ENABLED=true`. Disabled by default. Provider delivery queued after HTTP response; delivery failure needs monitoring/operational retry design before activation.
- Frontend: `dashboard/src/pages/EmailAccess.tsx` for registration/login/verify/reset. Login link is shown only if the backend returns `{enabled:true}`. Removed hard-coded win rate/PnL/ticker claims from sign-in.
- Local regression: original verification and external blockers are retained in this release evidence log.
- **Not release certified:** FastAPI route-level integration, npm bundle build and browser E2E, Resend sandbox/domain delivery, database concurrency/failure injection, CSRF/Origin staging checks, and live AWS data compatibility.


## Phase 05–06 archived handoff notes

# Phase 05/06 verification and release conditions

This candidate extends the Phases 01–04 engineering source. Nothing in this folder has been deployed to AWS, Cloudflare, or GitHub during this pass.

## Implemented and locally tested

- Google Sign-In and the old administrator TOTP routes remain present and unmodified.
- Separate email identity with pending verification, one-use 20-minute token digests, and scrypt password hashing.
- No account row exists before email proof. Verified accounts start as Free with `is_admin=False`, even for addresses listed in the administrator configuration.
- Existing Google identity emails are not auto-linked; disabled accounts cannot be used for reset/login.
- Password resets revoke all existing user sessions and send account-security mail only. Email send failures after resetting a password don't reverse the password change.
- SQLite-persisted per-email/per-IP throttles and generic request acknowledgements. Background mail delivery avoids synchronous provider round-trip differences in public response timing.
- Browser forms are behind an API-reported feature flag. The sign-in screen no longer presents invented live metrics.

## Verification in this workspace

`python -m pytest -q` and `python scripts/check_monorepo_contract.py` were executed. TypeScript syntax was parsed with globally installed TypeScript; `npm ci` failed inside this runner (npm internal exit handler failure), preventing build, lint/typecheck, and browser E2E.

## Explicit blockers before enabling email accounts

1. Build a staging image from this exact source and restore a backup of the current SQLite database; verify the three additional tables are created without changing existing users or trading data.
2. Verify FastAPI `/auth/email` route behavior, cookie flags, CORS/CSRF and session revocation with the actual auth library stack (currently unavailable in this runner).
3. Verify sender domain, SPF/DKIM, Resend API key, failures/bounces, opt-in policy, and safe delivery retry behavior. BackgroundTasks are best-effort and not a durable mail queue; consider a small durable outbox before production activation.
4. Verify login/signup/reset/expiry with a real browser against staging, including same-site cookies on custom Cloudflare/AWS hostnames and links with fragments. Confirm no credential or token goes to logs/analytics.
5. Conduct concurrent claim tests against production-like SQLite, abuse tests behind the actual reverse proxy, account enumeration timing tests, and session lockout checks.
6. Keep `EMAIL_ACCOUNTS_ENABLED=false` and `SECURITY_EMAIL_ENABLED=false` on AWS until **all** above conditions pass. In particular, the new `status` endpoint is present but returns false by default.

## Staging configuration (not production instructions)

- `FRONTEND_URL` points to the staging frontend HTTPS origin.
- `EMAIL_ACCOUNTS_ENABLED=false` and `SECURITY_EMAIL_ENABLED=false` initially.
- A verified Resend sender and server-only `RESEND_API_KEY`/`SECURITY_EMAIL_FROM` must be present when enabling the email test.
- The existing `main.py`, Docker Compose service name, Redis storage, scheduler, and database mount must remain compatible. Ensure paper-only mode throughout staging tests.

The next priority is Phase 06 responsive/browser QA and Phase 07 trading fault-injection tests. There is no live-trading certification from this source package.


## Phase 07–09 local completion batch — 2026-10-20

- Phase 07 design delivery is consolidated in `PHASE_07_DESIGN_DELIVERY.md`: route/action/role inventory, page hierarchy, high-risk interaction states, responsive rules and accessibility targets. Dashboard rows now activate with Enter/Space, and reduced-motion preferences suppress nonessential CSS motion. Screenshot sign-off and WCAG/browser review remain open.
- Phase 08 source work completed for the remaining route surfaces already present in the candidate, added an accessible stale/awaiting-data WebSocket indicator, and enforced a production bundle budget after build: 2.5 MiB total JS/CSS, 450 KiB largest JS chunk and 160 KiB largest CSS chunk. Browser E2E, role journeys, long-table profiling and screenshots remain open.
- Phase 09 adds validated request IDs, request-context logging and route-template/status/latency metrics at admin-only `GET /api/system/metrics`. Metrics are process-local and intentionally bounded; cross-process monitoring/alerting and end-to-end scan-to-exchange trace continuity require deployment instrumentation. Proposed backup/restore and isolated fault-drill policy is in `docs/operations/PHASE_09_OPERATIONS_POLICY.md`.
- Added `tools/binance-history-collector/`: a standalone Docker-ready public-data exporter for per-coin config, 1h/4h candles, funding, symbol metadata and optional short-window 5m/1m candles. It excludes unfinished bars and refuses candle gaps. Six focused observability/collector tests pass; the collector was not run against Binance from this workspace.
- Full local verification: 294 Python tests passed; frontend lint, TypeScript project check, Vite production build and the bundle-budget gate passed. The build reports the pre-existing mixed static/dynamic `authStore.ts` chunk warning and npm's environment `http-proxy` config warning.
- Ledger: 149 total tasks; **4 VERIFIED, 106 IMPLEMENTED_UNVERIFIED, 39 PLANNED**. Phases 7/8/9: **11/12, 14/15, and 9/11 implemented-unverified**, respectively. No status was promoted to VERIFIED.
- External gates still open: approved desktop/mobile captures; browser accessibility and role E2E; TLS/proxy/firewall staging; Docker restart/fault drills; real Redis/database/broker failure exercise; configured encrypted off-host backup and successful restore; and measured production capacity/cost. No AWS, Cloudflare, staging host, broker, Redis production, or live account was contacted.
