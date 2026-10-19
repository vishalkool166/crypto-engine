# Engineering working protocol — prevention of forgotten scope and unsupported claims

## Authoritative state

- `MASTER_TASK_LEDGER.csv` is authoritative. `MASTER_TASK_LEDGER.json` and `TASKS_READABLE.md` are mirror views generated from the same data; update together within one change.
- Once assigned, **IDs never change or get reused**, even for cancelled tasks. New work gets the next ID for its workstream or a dedicated CR-linked ID.
- Statuses: `PLANNED` → `IN_PROGRESS` → `IMPLEMENTED_UNVERIFIED` → `VERIFIED`; use `BLOCKED` for actual prerequisites and `WAIVED` only with documented rationale and authorized sign-off (never imply safety approval from waiver).
- `Evidence` must include actual source commit, test report/log location, test command, environment, reviewer and limitations.
- An existing file/function is `present in source`, not a 'completed blueprint task' unless full acceptance is proven.
- Never treat a compile check, unittest, fake Redis or mocked exchange as a passed testnet/failure-drill gate.

## Before changing code

1. Locate task(s) by ID and verify dependencies.
2. Identify exact current code paths and callers; update the source inventory if new discoveries differ.
3. Write a short change proposal: expected behavior, affected endpoints/data, tests, failure/rollback handling.
4. For any strategy, risk, trading, broker, auth, or database change: add deterministic before/after regression and signed ADR if semantics shift.
5. Implement in isolated branch/commit; leave AWS production untouched and live trading disabled.

## After changing code

1. Re-run focused tests and all relevant existing tests.
2. Run lint/type/build and browser tests if frontend touched; if unable, explicitly mark `IMPLEMENTED_UNVERIFIED`.
3. Re-run negative permission/failure paths when security/trading state changes.
4. Review resulting diff, secret scans, dependency lock change and generated assets for accidental churn.
5. Write evidence record. Link exact task ID and validation to artifact/commit.
6. Update task ledger and mirrored readable view and changelog; release must list blockers and residual risks.

## Response/report-card contract after every implementation package

```text
Source fingerprint / commit:
Package name and tasks attempted:
Verified tasks: N (IDs)
Implemented but unverified: N (IDs)
Blocked: N (IDs and exact missing prereqs)
Regression baseline: command + passed/failed/skipped
Frontend: install/lint/type/build/E2E results
Security: changes, negative tests, unresolved severity
Trading: paper/testnet/live clearly identified
State migration / backup:
Screenshots or test evidence:
Next dependencies:
```

## Non-negotiable release practice

- Commit full editable source and reproducible build instructions. Do not replace source with static compiled assets.
- Default paper mode; no automatic push to production and no unapproved broker trade execution.
- Do not share credentials, OTP, private user data, production database, or live journal dumps.
- Keep internal engineering documents under `docs/engineering/`; configure static frontend build to exclude them.
- When no test environment/provider access exists, leave scope `BLOCKED` with a reproducible exact checklist for an authorized operator.

## Owner handoff: only things that require your environment later

- Sanitized AWS running revision and service topology (not needed to begin repository work).
- Authorized staging/testnet environment and exchange demo credentials **configured privately** (not pasted in chat).
- Resend sending domain verified in provider dashboard and key injected to secret storage privately.
- Permission to create/push a private GitHub repository and actual CI access if requested.
- Design acceptance of two reference screens for desktop/mobile and admin/user split; no need to decide a full color palette now.
- Explicit decision before any live deployment, cloud retirement, or live-capital enablement.
