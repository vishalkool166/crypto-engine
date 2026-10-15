# Engineering status and verification ledger

**Baseline:** consolidated source from the P0/P1 continuation; includes earlier security, order-intent journal, Angel One quota changes and trading-safety fixes. **This is not an approved live-trading release.**

## Verified locally in this handoff

- 139 isolated Python tests passed. This number includes existing tests plus shared UTC-session, replay-end-boundary, net-P&L and research-evidence-gate regression coverage.
- Python compilation succeeded.
- Binance read-only metadata shows all 18 configured USDⓈ-M perpetual symbols active (snapshot 2026-10-14). This is metadata validation, **not strategy validation**.
- Source research integrity: manifest hashing, required funding presence, chronological training/holdout boundaries, conservative simulator assumptions, dataset-end embargo.
- Docs reorganized into stable technical references, with one authoritative status ledger rather than many pass-specific root files.

## Implemented; not integration-certified

| Domain | Present in source | Remaining acceptance requirement |
| --- | --- | --- |
| API/session controls | Authentication, role restrictions, WebSocket boundary changes | Authenticated HTTP/WS end-to-end penetration and authorization tests |
| Order safety | Durable intent reservation, ambiguous-response stops, live off by default | Binance testnet partial fills, crash recovery, protective-order reconciliation |
| Account risk | Drawdown, loss limits, fail-closed position checks | Real broker equity integration and operational circuit-reset drill |
| Angel One API | Redis Lua quota admission, caches and endpoint cooldowns | Real Redis/SmartAPI multi-worker and broker-policy verification |
| Strategy signals | Per-coin ADX/TP/session, shared session policy, safer calculations | Historical OOS comparison for 18 symbols; tick-level execution validation |
| Reliability | Offline tests, container configuration and documented runbooks | Actual Docker deployment, DB restore and incident simulations |
| Frontend | Separate React/Vite source retained unchanged; source-check workflow added | Dependency install, build, API contract and browser E2E tests |

## Blocking constraints observed here

- No complete 18-coin OHLCV-plus-funding dataset in the uploaded archives; Binance bulk-data endpoint unavailable from the runtime.
- Python `ta` dependency unavailable here. The existing unit tests run with deterministic/mocked indicator pathways.
- Redis/Angel One and authorized Binance testnet credentials were not connected; never request secrets in chat.
- No working Docker daemon and no cached npm dependencies for a frontend build. Deployment and frontend acceptance are unverified.

## Required sign-off sequence

1. Acquire immutable research datasets and run all-coin walk-forward experiments; preserve raw evidence and negative results.
2. Verify security and trading safety with real Redis plus Binance demo/testnet under failure injection.
3. Confirm database migration/restore and reconciled broker equity; validate deployment observability and rollback.
4. Build both repos on clean systems, run API contracts and E2E tests; only then evaluate any release-readiness claim.

All historical profitability claims are **NOT EVALUATED** as of this delivery. Strategy tuning, range trading and live-mode activation are intentionally not auto-applied.

The research-evidence gate (`python -m backtest.evidence`) defaults to **not approved**, and refuses to mark a study complete if any required symbol, funding, metric or fold is missing. A positive simulated holdout is only eligible for human research review, never production approval.

CI source-check workflows are included for backend and frontend. Their hosted runs were **not executed in this isolated session**; a workflow file is not evidence of a passing CI deployment.
