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
| Frontend | Redesigned React/Vite source lives in `dashboard/`; Cloudflare Pages build output is `dashboard/dist/`. Backend static fallback remains at `frontend/`. | Browser-based visual/E2E review against a running API; production edge routing and TLS validation |

## Blocking constraints observed here

- No complete 18-coin OHLCV-plus-funding dataset in the uploaded archives; Binance bulk-data endpoint unavailable from the runtime.
- Python `ta` dependency unavailable here. The existing unit tests run with deterministic/mocked indicator pathways.
- Redis/Angel One and authorized Binance testnet credentials were not connected; never request secrets in chat.
- The frontend production build succeeds locally. Lint still reports unused-symbol and hook-dependency warnings. Build success does not replace browser/API acceptance.
- Stripe checkout is not implemented in this bundle; paid plan purchase remains unavailable until backend checkout, webhook, and billing state are added and tested.
- The deployment config is aligned to `app.vishalkool.top`; production acceptance still requires edge routing for `/api`, `/auth`, and `/ws`, plus a valid certificate on the deployment host.

## Required sign-off sequence

1. Acquire immutable research datasets and run all-coin walk-forward experiments; preserve raw evidence and negative results.
2. Verify security and trading safety with real Redis plus Binance demo/testnet under failure injection.
3. Confirm database migration/restore and reconciled broker equity; validate deployment observability and rollback.
4. Build the backend and dashboard from the preserved `crypto-engine/dashboard` layout on a clean system; run API contracts and E2E tests before evaluating release readiness.

All historical profitability claims are **NOT EVALUATED** as of this delivery. Strategy tuning, range trading and live-mode activation are intentionally not auto-applied.

The research-evidence gate (`python -m backtest.evidence`) defaults to **not approved**, and refuses to mark a study complete if any required symbol, funding, metric or fold is missing. A positive simulated holdout is only eligible for human research review, never production approval.

Hosted CI and production deployment were not run in this handoff. A local build is not evidence of a passing production deployment.
