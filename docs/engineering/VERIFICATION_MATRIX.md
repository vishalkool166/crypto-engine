# Verification matrix and evidence gates

**Legend:** `UNIT` local deterministic test, `INT` integration with real service, `E2E` browser/user flow, `TESTNET` authorized broker environment, `OPS` staged operational drill, `REVIEW` independent examination. For a gate, attach actual logs, commands, and environment. Test plan entries are **NOT test results**.

| Test ID | Priority | System/negative scenario | Method and expected result | Depends on tasks |
|---|---|---|---|---|
| VT-001 | P0 | Legacy baseline | Run all Python tests, capture exact count and pass/fail/skip; golden fixtures stable | SE-00-005, SE-10-001 |
| VT-002 | P0 | Fresh clone | Clean Python install and npm ci offline from private AWS registry; should work via documented public/approved registry | SE-01-004, SE-01-005, SE-10-002 |
| VT-003 | P0 | Frontend type/build | ESLint, TypeScript noEmit, Vite build and serve; no runtime missing bundle | SE-10-002 |
| VT-004 | P0 | API schema | OpenAPI generation; compare routes, validation and frontend types | SE-02-004, SE-10-003 |
| VT-005 | P0 | Role matrix | Anonymous/free/pro/elite/admin, forbidden endpoints all 401/403 with no sensitive payload | SE-03-003, SE-10-003 |
| VT-006 | P0 | Horizontal data isolation | User A cannot read user B signals/accounts/keys/sessions if multi-tenant data applies | SE-03-003 |
| VT-007 | P0 | WebSocket auth | Anonymous, forged Origin, expired and wrong-tier sessions cannot receive protected events | SE-02-007, SE-03-003 |
| VT-008 | P0 | Session security | Logout and revoke invalidate API and WebSocket; secure cookie/CSRF policy tested | SE-03-005, SE-03-013 |
| VT-009 | P0 | OAuth | Unsolicited callback, state mismatch, duplicate identity email, unverified claims rejected | SE-03-006 |
| VT-010 | P0 | Login throttling | Concurrent brute force and Redis outage do not bypass security limit | SE-03-004 |
| VT-011 | P0 | Resend verify | Expired, replayed, purpose-swapped and wrong-user tokens fail; new verified user succeeds | SE-03-008, SE-03-011 |
| VT-012 | P0 | Resend reset | No enumeration, proper step-up/session revocation, provider outage not blocked trade | SE-03-010, SE-03-011 |
| VT-013 | P0 | Email scope | Test only allowlisted account/security templates exist; no trading email hook or digest | SE-03-012 |
| VT-014 | P0 | Secrets | No keys in Git or bundle, errors/logs do not leak TOTP, provider or broker token | SE-03-007, SE-10-008 |
| VT-015 | P0 | Bad OHLCV | NaN, zero, stale or still-open candle causes no new live exposure | SE-04-002 |
| VT-016 | P0 | Order timeout | Ambiguous submit creates unresolved intent and NO second submit | SE-04-003, SE-10-005 |
| VT-017 | P0 | Crash at journal edge | Kill process before/after local commit and broker response; no duplication on startup | SE-04-003, SE-04-011 |
| VT-018 | P0 | Partial fill and protection | Local/remote quantities, remaining orders and stops verified or clear halt for manual action | SE-04-004, SE-11-008 |
| VT-019 | P0 | Risk / kill switch | Unknown account equity, sticky breaker and risk-budget failures halt exposure | SE-04-005, SE-04-009 |
| VT-020 | P0 | Exchange precision/rates | Dynamic symbol filters, notional bounds, rate-limit handling tested with responses | SE-04-008 |
| VT-021 | P0 | Indian quota | Redis Lua in Redis 7 under two processes enforces per-client limits | SE-05-002, SE-10-004 |
| VT-022 | P0 | Angel One cooldown | Historical rejects isolate historical only; LTP unaffected; no uncontrolled retry | SE-05-003, SE-05-007 |
| VT-023 | P0 | Static egress | Authorized Angel One requests use expected registered outbound IP where required | SE-05-004 |
| VT-024 | P0 | DB migration | Existing anonymized SQLite copy migrates/rolls back, journaling preserved | SE-06-002 |
| VT-025 | P0 | Restore | Consistent WAL/SQLite/runtime backup restores and retains unresolved order intents | SE-06-004, SE-09-009 |
| VT-026 | P0 | Duplicate scheduler | Multi-process startup cannot duplicate 30s monitor or signal scans | SE-02-009, SE-09-007 |
| VT-027 | P0 | Pagination | 501+ synthetic rows, page 25/50/100, totals/sort/search across whole dataset | SE-02-006, SE-08-002 |
| VT-028 | P0 | Query refresh | Changing filter updates cache key; mutation invalidates all affected pages | SE-08-003, SE-08-004 |
| VT-029 | P0 | Live data in history | WS event doesn't silently jump to page one or reorder active page | SE-08-011 |
| VT-030 | P0 | Browser roles | Demo, free, paid and admin test every intended route/action with correct denial | SE-08-009, SE-10-006 |
| VT-031 | P0 | Responsive and accessibility | 320/390/768/1024/1440 px screens, keyboard and focus, critical controls remain usable | SE-08-013 |
| VT-032 | P0 | Demo/truth | Mock, simulated and exchange-derived values always labeled; no demo order side effects | SE-08-012, SE-06-012 |
| VT-033 | P0 | Redis/DB down | Backend correctly shows degraded status and rejects unsafe market/broker actions | SE-09-008 |
| VT-034 | P0 | TLS/proxy | Forwarded host/IP, cookies and WS upgrade correct behind intended reverse proxy | SE-09-003 |
| VT-035 | P1 | Performance | Cold/warm bundle, long trade lists and WS update render time measured, no target invented | SE-08-015 |
| VT-036 | P1 | Strategy research | 18 coins, 4h/1h/funding hashes, walk-forward chronology, all omissions shown | SE-06-007, SE-11-007 |
| VT-037 | P0 | Staging cutover | Deploy update, verify API/WS/UI/session, restart and rollback without lost data | SE-11-005, SE-11-009 |
| VT-038 | P0 | CI integrity | Hosted GitHub required checks pass; actions permissions audited; artifacts versioned | SE-10-008, SE-10-009 |
| VT-039 | P0 | Final status | All open P0 risks listed; no claim of production ready without testnet and independent reviews | SE-11-010, SE-11-011 |

## Evidence record schema (required for each claimed verification)

```yaml
id: SE-XX-YYY
status: VERIFIED
source_commit: <git SHA>
environment: <OS / Python / Node / Docker versions / broker mode>
executed_at_utc: <ISO-8601>
command: <exact reproducible test command, no credentials>
result: <counts, exit code, measurable behavior>
artifacts: <test report / log / screenshot / trace location>
reviewer: <who checked it>
limitations: <what this does not establish>
```

**Historical baseline:** During blueprint generation `python -m pytest -q tests` completed 139/139 green in ~1.42s in this environment. It only proves that particular isolated suite on this source snapshot. All VT cases above remain **unexecuted** until evidence is attached. Do not infer exchange/testnet integration, frontend install, security penetration test or live runtime from old passing tests.

## Release gate checklist

- `G-A` GitHub-ready = VT-001, 002, 003, 004, 014, 038 + docs/source migration checks.
- `G-B` Working paper/demo app = VT-005 through 013, 024 through 034, 037 + security review findings disposition.
- `G-C` Broker testnet and operational safety = VT-015 through 023, 025, 026, 033, 037 + operator drills.
- `G-D` Research integrity = VT-036 plus independent review of report and completeness.
- `G-E` Live capital = ONLY after explicit human authorization and independent review of G-A–D, current deployment credentials, exchange conditions and incident response. Never automatically enabled.
