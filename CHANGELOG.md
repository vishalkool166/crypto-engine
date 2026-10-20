## Unreleased — dashboard accessibility follow-up (2026-10-20, local only)

- Added modal semantics, keyboard focus containment, initial focus and focus return to mobile navigation; named collapsed sidebar controls for assistive technology.
- Browser-based responsive and accessibility approval remains pending until the dashboard can be served and reviewed.

## Unreleased — repository handoff cleanup (2026-10-20, local only)

- Rewrote the root README as a concise project, development and deployment guide; added a documentation index.
- Added an environment-variable reference and completed the safe placeholder inventory in `.env.example`; live-order override remains intentionally absent.
- Added a static environment-template check to the manual verification script; it passed against the current Python source and documents generated, test-only and dangerous or unsupported variables.
- Replaced the chronological release-evidence log with one current status and gate summary. Older test counts are not presented as current verification.
- Removed the superseded initial assessment and generated TypeScript build metadata; ignored future `*.tsbuildinfo` files.
- No application code, strategy parameters, AWS runtime files or deployment configuration were changed.
- Local monorepo, source-hygiene, task-ledger, API inventory, Indian paper-scope and S0 checksum checks pass. Full Python/OpenAPI/schema verification could not be reproduced in this workspace because runtime dependencies are absent.

## Unreleased — Phases 04–06 local continuation (2026-10-20, not deployed)

- Hardened Telegram webhook controls with shared Redis update replay claims, explicit sender allowlisting for `/scan`, `/backfill`, and `/discard`, a narrow configured private-chat fallback, and durable audit-before-mutation behavior. Replay protection or audit failure blocks mutating commands.
- Changed startup reconciliation to preserve local active trade records and enter `reconciliation_required` with a durable new-exposure halt when exchange snapshots are unavailable, positions are missing or mismatched, or orphan positions are found. No automatic close assumption is made.
- Added admin-only regression tests for manual Indian data refresh and quota diagnostics; added LTP TTL expiry and failed Angel One refresh preservation tests.
- Added the missing ML dataset module with fixed entry-time features and closed-outcome labels. Trainer evaluation now reserves the latest chronological 20% as an untouched holdout; it is not used for model fit or calibration.
- Bounded chatbot messages to 2,000 characters, marked retrieved RAG context as untrusted evidence, and labeled backtest P&L as simulated with `exchange_verified=false`.
- Added a chronological ML dataset and isolated latest-window evaluation, copying signal-time factors into durable outcomes; regression tests confirm exit-only fields are excluded. Full local gate: 288 Python tests passed, plus frontend lint, typecheck, and production build.
- No real Redis, broker, exchange testnet, historical 18-symbol research data, staging, AWS, or independent review was available; related gates remain open.

## Unreleased — Phase 04 execution control continuation (2026-10-20, local only)

- Added a durable operator kill-switch for new exposure, gated reset on fresh exchange/local-trade/order-journal reconciliation and explicit confirmation, and preserved reduce-only exits while halted. Malformed halt state blocks new entries.
- Added order-journal schema versioning with safe legacy metadata backfill and rejection of unsupported future versions without deleting intent evidence.
- Made the local release audit fail unless configured trading mode is paper. This is a source-level gate, not a substitute for deployment approval.
- Unified both trading-mode API routes on one transition helper. The exchange client must close successfully before mode persistence and in-process config updates; a shutdown error no longer reports failure after silently switching the process mode.
- Added isolated regression tests for shutdown failure, operation order, resulting mode flags, and both routes using the helper. This closes one specific mode-transition defect; full role coverage, staging and live broker checks remain open.
- Added offline async coverage for limit-entry full fill, confirmed cancellation, and partial/ambiguous quantity states that require manual reconciliation. Protective order behavior and exchange testnet reconciliation remain open.
- Added a deterministic matrix for portfolio circuit tiers 0–6, sticky halt preservation, daily-stop fail-closed behavior and adaptive exposure reductions under circuit throttles.
- Added golden tests for canonical scoring/grade thresholds and verified market fetch drops the newest unfinished candle before signal indicators consume it. Existing per-coin targets, UTC session and rejection tests complete the source-only coverage for this acceptance.
- Added TOTP step-up and audit records to the scanner-start and monitor-stop execution controls. Invalid step-up is rejected; local route tests cover both outcomes. Broader endpoint authorization and browser/CSRF review remain open.
- Bound manual close requests to the stored active trade and its symbol/direction, rejected non-active trade IDs before exchange execution, and added audit outcomes for denied and completed close attempts. Offline route tests confirm mismatched client symbols cannot redirect a close.

## Unreleased — Phases 07–09 source candidate (2026-10-19)

- Changed session logout, market scan, and per-coin/all-coin backtest launch routes from GET to POST, and updated the dashboard client. Added regression checks so these state-changing/work-triggering routes cannot be reintroduced as GET; broader route inventory remains open.
- Repaired the frontend lockfile so a clean `npm ci` succeeds; fixed TypeScript, lint, hook-order and API-data shape failures found by running the previously unverified frontend gates.
- Added route-level lazy loading. Local build output now separates page chunks; largest route-independent initial JavaScript bundle is 231 kB raw (about 70 kB gzip).
- Verified the Python suite in an isolated Python 3.12 environment (204 passed); Node 24 frontend lint, type-check and production build pass. Python 3.11, browser E2E and Cloudflare staging remain open.

- Preserved the 15-file strategy S0 baseline with SHA-256 verification; no trading strategy or risk parameters changed.
- Added isolated tests for monitor timeouts and empty position responses (no inferred closures).
- Corrected logout to return to Cloudflare and WebSocket ping deduplication to track hashes per user tier.
- Removed the redundant machine-generated JSON copy of the 141-task engineering ledger; CSV remains canonical.
- Consolidated Phase 05–06 handoff notes into release evidence and added a read-only release gate audit.
- Retained original AWS Dockerfile/Compose, config, scheduler and exchange code; production rollout is still unverified.

## Unreleased — Phase 05 email accounts and partial Phase 06 frontend cleanup

- Added a feature-flagged email identity: pending verification, time-bound one-use tokens, password login/reset and session revocation. Google and admin authentication remain separate.
- Added a restricted account-security email delivery flow and verified-email frontend pages.
- Removed hard-coded price, win-rate and PnL figures from the public login page.
- No production deployment; integration, browser, provider delivery, and trading safety verification still required.

# Engineering candidate: Phases 03–04 (2026-10-19)

- Corrected Redis status source: administrator-only `/api/system/health` instead of treating liveness JSON as a Redis probe. Preserved `/api/health` for Compose.
- Corrected System dashboard unknown/unavailable health state and admin-only diagnostics polling.
- Linked Pricing and Profile to the server-side catalogue and entitlements; removed false eight-hour delay and unsupported UI feature promises.
- Hardened Google account provisioning, identity linking and disabled-user checks; repaired missing legacy subscription rows.
- Enforced invalid tier rejection, verified Google email claims and fail-closed session creation.
- Added 8 regression tests including a legacy mixed-case email identity check; **181 Python tests pass, 1 skipped**. All deployment/browser gates remain open.
- Consolidated 14 obsolete/duplicate engineering documents into maintained architecture, operational, planning and release-evidence references; updated the 141-task ledger to remove GitHub Actions assumptions without inflating task completion.

# Changelog

## Unreleased — Offline engineering continuation (2026-10-20, not deployed)

- Added a source schema inventory for all 31 SQLAlchemy tables and a storage/backup boundary document; neither claims to describe the live AWS database or mounts.
- Added a deterministic CycloneDX SBOM generator for Python runtime/test requirements and the npm lockfile, with manifest hashes and a stale-artifact check.
- Documented the current Indian integration as market-data/signal/paper scope and added a release guard against direct SmartAPI order-placement calls in the scoped modules.
- Added Indian IST market and ORB boundary cases. Holiday calendars and broker/staging behavior remain unverified.
- Extended order-journal concurrency coverage across separate processes. The test exposed and fixed a first-connection SQLite WAL mode race using bounded initialization retries; broker-side reconciliation remains open.
- Added an explicit signal-quality report stating **NOT EVALUATED** because approved immutable candle/funding data and completed holdout reports are absent. No strategy parameters were changed and no performance figures were invented.
- Added `/api/ready` to report sanitized database/Redis readiness separately from process liveness; local failure tests verify degraded state maps to HTTP 503.
- All changes are local only; AWS, Cloudflare, GitHub, Resend, Google OAuth and exchange accounts were not accessed.

## Unreleased — Phases 02–03 continuation (2026-10-20, source candidate only)

- Added a source-generated API authorization inventory covering 129 HTTP/WebSocket route operations and checks that fail when routes are added without an explicit policy classification.
- Added OpenAPI release validation for registered/documented method parity, unique operation IDs, metadata and WebSocket registration (124 documented HTTP operations).
- Added a Phase 03 threat model and recorded remaining OAuth, browser, tenant-isolation, provider-delivery and deployment checks.
- Hardened personal API keys in SaaS middleware: hashed storage, 90-day expiry for newly created keys, safe-method-only access, no inherited administrator role, SQLite-safe expiry comparison, and owner-scoped revoke. Existing legacy keys without expiry require rotation; the global dashboard key remains privileged.
- Validated API-key creation input and added rate limiting. Added regression coverage for OAuth identity claims, cookie-origin guard behavior, route classification and API-key scope.
- Preserved the exact upstream AWS `auth.py` hash. No deploy, push, provider account, production database or exchange account was accessed.
- Local verification: `scripts/verify_local.sh` passed with **218 Python tests**; frontend lint, TypeScript build check and Vite production build passed on Node 24.19.0 / npm 11.9.0. Browser and staging checks remain open.

## Phase 01–02 candidate — 2026-10-19 (not deployed)

- Audited the current source and preserved core AWS root-level runtime names, Compose services, volumes, and trading logic.
- Removed legacy `frontend/` compiled assets and FastAPI static/Jinja SPA serving from the **candidate only**; known AWS browser routes now redirect to the configured Cloudflare frontend.
- Routed OAuth failures back to Cloudflare login; added bounded, validated frontend-origin redirect helper and regression checks.
- Removed the invalid Cloudflare Pages `_redirects` catch-all; deep-link behavior needs deployed browser verification.
- Google Sign-In remains. Feature-gated email/password registration, verification and password recovery were added in the later Phase 05 source candidate; they remain disabled pending staging and provider verification. Resend is for account/security messages only.
- Local verification: 173 Python tests passed, one module skipped. Staged Docker and browser tests are outstanding.


## 1.0.0-rc1 — 2026-10-19 (source candidate, not production-certified)

This is a **release candidate**, not approval to merge to the AWS auto-deploy branch or to place live orders.

- Full-dataset admin user search and audit search/status/action filtering performed before pagination, with bounded queries, stable ordering and new isolated SQLite regression tests.
- Admin list screens use the shared pagination component; User table scrolls when space is limited. Original light/dark CSS variables and Outfit/Geist fonts remain unchanged.
- Added a page-level React error boundary that avoids displaying internal exception details to users.
- Added private no-store cache headers on auth/API responses and an optional, unit-tested session Origin guard. Guard remains **off by default** until staged browser tests.
- Added independent Cloudflare build environment validation for configured HTTPS API/WSS endpoint origins; no credentials included in frontend builds.
- Added integrity-checked **restore-to-new-file-only** SQLite operator utility and recovery tests.
- Added `SECURITY.md`, `CONTRIBUTING.md`, manual task-ledger validator and machine-readable v1 candidate release gates.
- Existing trading algorithms, Docker/Compose root paths, settings/config/scheduler/credential logic, GitHub repo identity, and original frontend palette retained.

## 0.2.0 — 2026-10-19 (engineering candidate; not deployed)

- Unified source layout around existing `crypto-engine` AWS root with editable React `dashboard/` for Cloudflare Pages.
- Retained AWS static `frontend/` fallback; removed GitHub Actions workflows as directed.
- Repaired initial server pagination for signals/trades, shared DataTable sorting, Overview/navigation hierarchy, private PWA caching and hard-coded frontend-to-backend API routing.
- Security-only Resend delivery adapter provided but **inactive**. Existing account credential and TOTP workflows unchanged.
- Added local verification scripts and two-host AWS/Cloudflare rollout playbook.
