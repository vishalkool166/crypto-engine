# Indian-market integration scope

## Current source boundary

The current Angel One integration is for authentication/session management, market data, instrument metadata, ORB analysis, quota control, and paper/signal tracking. Indian signal tracking is stored as `TradeJourney` evidence; the source path is not an order execution adapter.

`scripts/check_indian_paper_scope.py` scans `api/indian.py` and the Indian engine modules for direct SmartAPI order-placement or modification calls. Keep this guard in local release checks. Any future Indian order execution requires a separately reviewed design, explicit authorization, broker-policy validation, idempotent journaling, and paper/testnet drills before implementation.

## Runtime and data caveats

- Angel One authentication and market data still depend on configured credentials and Redis-backed quota controls.
- Redis outage blocks quota admission; source checks do not prove the deployed Redis version, multi-worker atomicity, or persistence.
- Market-time gates currently use IST clock windows. A source review cannot establish exchange holidays, exceptional sessions, or stale-data rejection without dated fixtures and broker integration tests.
- This scope statement does not certify that live Indian execution is impossible through every indirect or dynamically invoked path. The guard catches direct SDK calls in the scoped source modules; independent review is still required before a beta.

## Verification still required

Run the market calendar and stale-data tests, Redis concurrency/outage tests, static-IP and broker-policy checks, and cross-market failure isolation tests. Do not label those complete from this local static audit.
