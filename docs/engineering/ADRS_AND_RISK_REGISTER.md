# Decisions, pending ADRs and risk register

## Existing source decisions to preserve unless revisited

- Existing docs `DECISIONS.md` ADR-001: Keep Python execution backend; don't force rewrite.
- ADR-002: Ambiguous order outcome means no repeat order and durable journal/reconciliation.
- ADR-003: Historical strategy results cannot self-certify profitability.
- ADR-004: Shared UTC session semantics across research/live.
- ADR-005: Legacy `sl`/`tier` per-coin values not silently reinterpreted.
- ADR-006: Source documentation describes evidence, not invented project history.

## New provisional decisions (explicitly reversible)

| ADR | Status | Decision | Alternatives / reason | Revisit when |
|---|---|---|---|---|
| ADR-007 | PROPOSED | One private GitHub monorepo | Split repos require coordinated versions; simplify shared API and CI | External independent product teams/scaling |
| ADR-008 | LOCKED USER SCOPE | Resend for account setup/security only | Telegram continues trading alerts; email must not carry signals/reports | Only explicit new user instruction |
| ADR-009 | PROPOSED | Keep existing trading engine algorithms and Python runtime | Unnecessary rewrites invalidate golden results | Proven bug / signed algorithm ADR |
| ADR-010 | PROPOSED | Modern, calm financial dashboard with separate admin workspace | Controls information density while retaining functionality | UX reference approval |
| ADR-011 | PROPOSED | Server pagination for expanding histories | Current client truncation/sort indicators are misleading | API usage benchmarks |
| ADR-012 | PROPOSED | Single-leader scheduler and single durable SQLite writer topology | Avoid multi-instance orders/jobs and DB divergence | Dedicated transactional DB migration |
| ADR-013 | PROPOSED | Monorepo engineering docs stay out of public bundle | Protect internal threat model/ops runbooks | Document publication review |
| ADR-014 | DEFERRED | Launch-default light vs dark visual theme | Both should work; defer polish until layouts validated | UX review |
| ADR-015 | DEFERRED | Whether to unify OAuth + legacy dashboard credentials | Identity migration risk; review actual users and recovery policy | After security inventory |
| ADR-016 | DEFERRED | Cloud provider/EC2 retirement | Out of scope; test costs and reliability separately | Owner asks for migration |
| ADR-017 | DEFERRED | Licensing and open-source decision | Ownership and downstream obligations unclear | Before public publication |

## Risk register

| Risk ID | Severity | Evidence / impact | Mitigation and proof | Linked tasks |
|---|---|---|---|---|
| R-01 | Critical | Trading error could create unintended real exposure | Live off default, journal and broker testnet drills, manual reconciliation runbooks | SE-04-003, SE-04-004, SE-11-008 |
| R-02 | Critical | EC2/source divergence unknown; source ZIP lacks live data | Inventory production revision safely, backup/restore before deploy | SE-00-002, SE-06-004 |
| R-03 | High | AWS CodeArtifact lockfile blocks clean frontend clone | Regenerate verified lockfile and test npm ci clean | SE-01-004 |
| R-04 | High | API role/session/websocket vulnerabilities not penetration-tested | Authz matrix, CSRF/Origin/OAuth reviews, browser E2E | SE-03-003, SE-10-003 |
| R-05 | Critical | Scheduler in app could duplicate work if replicated | Single logical leader and multi-worker failure/restart test | SE-02-009 |
| R-06 | High | SQLite WAL/journal loss or unsafe migration | Backups with SQLite API, safe migrations, restore drill | SE-06-002, SE-06-004 |
| R-07 | High | Resend security token leak or reset account takeover | Hashed one-time expiry token, generic responses, verified sender, strict role/identity rules | SE-03-008, SE-03-011 |
| R-08 | High | Legacy dashboard auth and Google identity may conflict | Define linking policy before issuing account reset tokens | SE-03-002, SE-03-010 |
| R-09 | High | Private registry and unpinned Python packages compromise reproducibility | Deterministic locks, SCA, update policy, CI | SE-01-004, SE-01-005 |
| R-10 | Medium | Dashboard presents limited history as complete, sort UI lies | True server pagination, backend sort, query key fixes, E2E | SE-08-002, SE-08-003, SE-08-004 |
| R-11 | High | Angel One Redis quota tested mainly with stubs, unknown static IP | Real Redis multi-worker test and authorized broker networking test | SE-05-002, SE-05-004 |
| R-12 | High | Exchange WS stale/disconnected could show false 'healthy' | Data age provenance and degraded state, no-orders-on-unknown | SE-02-008, SE-04-002 |
| R-13 | High | Research data insufficient to support profitability claims | Immutable dataset + 18-symbol walk-forward and transparent untested labels | SE-06-006, SE-06-007 |
| R-14 | Medium | ML/RAG model memory and startup may degrade small EC2 VM | Measure footprint, optional startup, graceful failure and resource budgets | SE-06-010, SE-09-011 |
| R-15 | High | Accidentally bundling secrets/internal docs into frontend | Ignore/static build policies, secret scanning, ZIP content checks | SE-01-007, SE-03-007 |

Severity is qualitative; update with owner, likelihood, actual reproducible evidence and closed date on every milestone. **A risk is not removed from the register just because a patch exists.**

## Change-control template

```text
Change-ID: CR-YYYY-NNN
Reason / requester:
Requirement and affected task IDs:
Paths and external interfaces changed:
Behavior change? (signal, sizing, order, auth, API, migration)
Risk rating + rollback compatibility:
Decision (ADR if relevant):
Tests added + exact result:
Environment and broker mode:
Evidence refs:
Approval / date:
```

Use this for any unplanned feature, changed invariant, new service or major repository reshuffle. Never silently overwrite approved ledger tasks; amend with dated reasoning.

## Implementation ADR-2026-10-19 — Release candidate rather than unearned R5 sign-off

The unverified dependency install (`npm ci` failed due no DNS), unavailable Docker engine, unconnected Resend verified domain, lack of AWS/testnet credentials and independent security review prevent declaring full R5 completion. The source package remains a local engineering candidate with honest gates.

- Old frontend static builds removed from source. Root Dockerfile compiles editable React into backend static root. Direct backend operation without a build displays an explicit placeholder.
- Vite dev proxy defaults to localhost; authenticated API runtime caching removed from PWA; old `api-cache` cleared by client on next load.
- The account-security Resend transport has no trade or performance email capability and is disabled by default. **Do not activate password reset or email verification until one-time token storage, authorization, expiry, replay prevention and identity-migration tests are implemented.**
- `trade/monitor.py` history filtering now uses consistent query predicates for count/page, but brokerage reconciliation and schema migration were not exercised.
- Existing frontend subscription gating and admin-only broker endpoints contain a role-contract mismatch requiring a policy decision; never respond by exposing shared broker positions to ordinary subscribers.
