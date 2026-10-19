# Signal Engine — Master Engineering Blueprint v1.1 (AWS + Pages deployment)

**Status:** implementation-ledger baseline; see ADR-002 for newer architecture • **Artifact type:** controlled implementation specification • **Audience:** owner, implementer and independent reviewer.
**Source-of-truth tracker:** `MASTER_TASK_LEDGER.csv` (mirrored as JSON and readable Markdown).
**Scope lock:** The original source archive remains protected; no deployment, trading enablement or source rewrite is authorized by this blueprint.

## 1. Product outcome

Deliver a **private, maintainable GitHub monorepo** containing the complete editable Signal Engine backend and frontend, automated checks, clean installation, deployment files, tested operational recovery, and a user-focused financial dashboard. Preserve the existing Python trading algorithms and the exchange-order safety model unless a separate change request documents and verifies the difference.

A 'proper repository' has evidence that another engineer can clone, understand, test, build, operate and recover it. It is **not** equivalent to (a) profitable strategy, (b) full exchange safety, or (c) approval to trade with real money. These require independent evidence gates.

## 2. Non-negotiable requirements

1. Preserve canonical **18-coin** strategy configuration, scoring, closed-candle policy, UTC session semantics, and sizing/risk decisions until comparative golden tests justify any change.
2. **Default to no live orders.** Unsafe/unknown broker, account, market data, journal or database state must block *new exposure*. Preserve protective-risk handling separately.
3. Never emit duplicate orders on ambiguous responses; record intent before submission, reconcile broker truth, and escalate uncertain state.
4. Preserve existing SQLite order journals and unresolved positions; never replace production volumes with example data or perform unreviewed schema resets.
5. Keep Binance crypto and Angel One India market integrations separated. Indian market remains data/paper signals according to source; no unreviewed order placement.
6. Resend handles **only** account setup and security: verification, activation, password recovery, email change, account security changes and relevant security alerts. No signals, trade changes, engine status, performance summaries, marketing or general notifications by email. Telegram remains trading-alert channel.
7. Frontend is a clear **modern financial operations product**, not a terminal aesthetic or generic template. User and admin workflows separated; accessibility, mobile, working controls and correct pagination required.
8. No hardcoded secrets, hidden production dependencies, fake metrics, skipped tests counted as passes, or misleading green status indicators.
9. Preserve an untouched source snapshot; start with a clean, private monorepo; do not publish engineering/internal ops docs in the frontend build.
10. Document what cannot be tested; never turn a hypothetical capability into a verified status.

## 3. Project reference architecture (target, not implementation claim)

```text
crypto-engine/                   # existing private GitHub repository
├── main.py config.py scheduler.py auth.py   # existing AWS import root
├── agents/ engines/ trade/ api/ saas/ tests/ # unchanged top-level layout
├── Dockerfile docker-compose.yml           # existing AWS runtime contract
├── frontend/                      # old compiled AWS-served assets (temporary fallback)
├── dashboard/                     # source React/Vite/TS -> Cloudflare Pages dist/
├── docs/engineering/              # private planning & evidence; not Pages assets
├── docs/operations/               # AWS/Cloudflare deployment runbook
└── scripts/                       # owner-run local checks (no GitHub Actions)
```

This is the adopted placement. Preserve AWS entrypoints and unit tests. The original backend `frontend/` compiled build is retained for AWS compatibility; `dashboard/` is the editable UI source. See ADR-002.

## 4. Execution order — coherent work packages

| Package | Objective | Phase IDs | Exit criterion |
|---|---|---|---|
| **R0 — Baseline** | Freeze, map and prove as-is behavior | 00 | Hashes, API/role/job/data inventory, baseline tests, unknowns ledger |
| **R1 — Foundation** | Git-safe monorepo and clean builds | 01 + parts of 02/10 | Fresh backend/frontend installs, deterministic build, safe config, owner-run local quality checks |
| **R2 — Security + API** | Security foundations, Resend, backend contracts, data migrations | 02/03 + 06 | Auth/role tests, reset/verification flows, migration staging and API schemas |
| **R3 — Trading + research correctness** | Preserve/exercise execution invariants and external adapters | 04/05/06 | Paper/testnet fault drills, Redis Lua verification, parity snapshots; no live approval |
| **R4 — Product frontend** | UX foundation and functional page-by-page rebuild | 07/08 | Real filters/sorting/pagination, user/admin journeys, browser and responsive evidence |
| **R5 — Operations + release** | Containerization, observability, disaster recovery and gate review | 09/10/11 | Fresh clone, staging cutover/rollback, evidence pack, honest blockers |

Work streams can overlap when dependencies permit, but each package has a coherent full-source release, not dozens of cosmetic patch versions. **Each package must keep the app runnable in paper/demo mode.**

## 5. Required milestone package contents

Every implementation package must deliver:

- **Full monorepo source** (not a diff-only ZIP), with matching Git commit/source hash and version.
- Updated task ledger: newly `VERIFIED` tasks include evidence link, exact command, environment and verification result.
- Build/test summary: total/passed/failed/skipped, security findings, application startup health, known limitations.
- Change log, APIs and migrations affected, rollback/backup considerations, before/after regression notes.
- Frontend screenshots/browsable build when frontend changes are included; all demos distinctly identified.
- Release blockers and remaining P0 tasks visibly listed.

The final package should be ready to push to a **private** GitHub repository, but cannot claim GitHub deployment or local builds succeeded without logs from the actual environment. No production credentials or databases are included.

## 6. Gate hierarchy (do not collapse)

**G-A: Repository-ready.** Clean clone, all dependencies, Python tests, frontend lint/type/build, local verification scripts and docs are reproducible; no known secrets committed.
**G-B: Application-ready (paper mode).** Core UI and HTTP/WS behavior tested against real backend, database migrations/backups restored, security E2E, background jobs and failure behaviors exercised.
**G-C: Testnet-operational.** Broker integration, partial fills, uncertain submits, stops/TP, reconciliation, outages, on-call/rollback and operator drill pass.
**G-D: Strategy research reviewed.** Complete immutable 18-symbol historical datasets including funding, untouched walk-forward holdouts and cost assumptions; no performance guarantee.
**G-E: Live capital approval.** Independent security/risk/operational review with explicit user/operator authorization **after** G-A through G-D where applicable. This blueprint does not grant G-E.

If a gate cannot be exercised with currently available services, label `BLOCKED: requires staging/authorized broker/AWS access`, not `VERIFIED`.

## 7. Definition of Done (DoD) for EVERY task

1. Implementation reviewed against exact code path and acceptance text; requirements traced to tests.
2. Relevant previous regression tests remain passing; new test for repaired defect or new functionality exists.
3. Failure/unauthorized/empty/unavailable paths tested where the feature can alter funds, privileges, state or user trust.
4. Documented behavior, config and UI match actual implementation; defaults stay safe.
5. Evidence record added with test command, platform, result and date; reviewers can reproduce it.
6. No untracked scope or algorithm changes; ADR required for behavior-changing choices.

`IMPLEMENTED_UNVERIFIED` is not `VERIFIED`. A screenshot is not proof of a working API. A passing unit suite is not proof of production trading safety.

## 8. Priority and dependency policy

**P0:** security/trading integrity, reproducibility, core data, critical UI correctness and release gates. Blocking for relevant release.
**P1:** major completeness, research evaluation, documented quality improvements.
**P2:** explicitly deferred nonessential polish only, never hidden by claiming full completion.

The CSV's `Dependencies` column is authoritative. A task blocked by secrets, an unreachable broker, cost/capacity, design decision, or staging environment must carry the exact reason and a feasible validation path.

## 9. Out-of-scope unless separately approved

- Enabling real-money trading or claiming profitability.
- Migrating execution to Cloudflare Workers or changing cloud provider as part of repo cleanup.
- Changing signal thresholds, TP/SL rules, leverage or which symbols are enabled.
- Automating Angel One live order placement.
- Email notifications for trading signals, alerts, reports, or marketing.
- User-facing publication of the engineering ledger and internal runbooks.
- Replacing actual exchange reconciliation with simulated confirmations.

## 10. Open owner decisions (not needed to start R0/R1)

- Final brand visual mood: default a restrained modern product with **both light and dark** modes; choose launch-first theme after reference screens.
- Repository access and legal license: keep private by default until owner approves rights and permissions.
- Account policy: retain Google OAuth + dashboard/TOTP paths initially; decide whether to consolidate once inventory and migration impact are established.
- Deployment vendor: keep EC2 production untouched while testing; target elsewhere only through separate feasibility and rollback plan.
- Paid services: Resend sending domain and credentials required only at staging; never share secrets in chat.

## 11. Truth and anti-hallucination protocol

- A source path in this plan describes inspected code; it does **not** certify live operation.
- Every claimed completed task links to a diff, exact test command/result, and relevant operational proof.
- When uncertain, record `UNKNOWN` and the specific probe needed; do not infer production configuration from local source.
- When changing a fact, update the ledger, relevant architecture notes and a dated ADR/change entry in the same PR.
- Always report failed/skipped tests, external blockers and differences between paper, broker demo/testnet and live.
- Measure actual progress as `VERIFIED` task counts by priority/workstream, never invented percentages.
