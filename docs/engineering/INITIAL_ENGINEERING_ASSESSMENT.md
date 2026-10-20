# Initial engineering assessment

**Assessment date:** 2026-10-19  
**Source:** `Signal-Engine-Phases-01-09-Engineering-Candidate.zip`  
**Comparison source:** `Signal-Engine-Consolidated-Engineering.zip`  
**Scope:** Local source inspection and offline static checks only. Neither source archive is evidence of what is currently deployed.

## Findings

1. **Architecture.** One Python/FastAPI service remains at the repository root for the AWS runtime. It owns the APScheduler, exchange integrations, Telegram, SQLite/Redis state, API, Google OAuth and SaaS routes. The editable React/Vite client is under `dashboard/` for Cloudflare Pages. AWS remains the backend and execution boundary.
2. **Implemented in source.** The candidate includes the monorepo layout, Cloudflare frontend source, tier catalogue, account/session modules, optional email/password lifecycle, admin and API routes, order safety controls, a research/backtest path, backup/restore utilities, regression tests and an engineering task ledger. The release notes and ledger correctly describe most of these as unverified.
3. **Verified here.** `check_monorepo_contract.py`, `check_source_hygiene.py`, `check_task_ledger.py`, and `freeze_strategy_baseline.py --check` pass. The AWS runtime identity check confirms the candidate's Dockerfile, Compose file, config, scheduler, auth and trade monitor match the recorded upstream hashes. These are static/local checks, not application operation.
4. **Incomplete or unverified.** The ledger contains 141 tasks: 2 `VERIFIED`, 50 `IMPLEMENTED_UNVERIFIED`, and 89 `PLANNED`. The Python test suite could not run because `pytest` is absent in the available Python 3.12.14 environment. Frontend dependencies are absent, so lint, type-check, production build and browser journeys remain unverified. Docker, AWS, Cloudflare, Redis, Google OAuth, Resend delivery, broker testnet and staging access are not available in this audit.
5. **Duplicated or uncertain ownership.** `engines/crypto/strategy.py` contains a separate legacy scoring implementation. A source search found no reference from the current scanner path; the scanner calls `agents.signal_agent`. The legacy module should remain untouched until call-site and compatibility review is complete. Do not treat it as a second live strategy or benchmark.
6. **AWS compatibility.** `Dockerfile`, `docker-compose.yml`, `config.py`, `scheduler.py`, `auth.py`, and `trade/monitor.py` match the recorded upstream SHA-256 manifest. `main.py` has candidate changes, including frontend redirects and response cache/security behavior. The static guard passes, but a staging startup and OAuth/cookie/browser check is necessary before deployment.
7. **Security posture.** No secrets were reported by the repository's heuristic hygiene check; that check is not a full secret/history scanner. Email account features default disabled, and the Resend adapter enumerates account/security-only message types. Provider delivery and end-to-end identity controls have not been verified. The optional session Origin check remains off pending cross-origin browser validation. A full endpoint-by-endpoint authorization, OAuth state and dependency audit remains open.
8. **Live signal path.** `scheduler.job_scan()` calls `alerts.scanner.scan_all_coins()`, and the scanner invokes `agents.signal_agent.run()`. Research and backtest modules exist, but source presence and a frozen 15-file S0 hash manifest do not establish strategy parity or profitable performance.
9. **Evidence required for signal quality.** Obtain contiguous closed 1h/4h bars and funding history for the configured symbols; preserve dataset manifests and hashes; replay the actual S0 path with costs, conservative intrabar ordering, and explicit assumptions; run predeclared chronological walk-forward folds; report sample counts, expectancy, drawdown, trade frequency and uncertainty; then keep any candidate research-only until independent paper-forward evaluation.
10. **Prioritized next sequence.** (a) restore a compatible Python environment and execute the existing suite, (b) install frontend dependencies and run lint/type/build, (c) close source-level auth/API/trading-control gaps from the ledger, (d) run isolated Compose/Redis/SQLite failure and restore drills, (e) run browser journeys against staging with email flags off then test Resend in its sandbox, (f) acquire and hash research data and run preregistered OOS comparisons, (g) complete independent security and execution reviews, then (h) prepare—not execute—a repository migration until remote history rewrite is explicitly approved.

## Local checks performed for this assessment

| Check | Result |
| --- | --- |
| Monorepo/AWS compatibility static contract | Passed |
| Source hygiene heuristic | Passed; not a comprehensive secret scan |
| Task ledger identity/dependency validation | Passed; 141 tasks, 2 verified |
| S0 strategy source hash check | Passed; 15 files unchanged |
| Python tests | Blocked: `pytest` is not installed; no test count claimed |
| Frontend lint/type/build/browser | Blocked: `dashboard/node_modules` absent; not run |
| Staging or production integration | Not run; no infrastructure was accessed |

No deployment, remote Git operation, live exchange request, account-email delivery or production data mutation was performed.
