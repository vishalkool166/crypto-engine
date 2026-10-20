# Phase 09 — Local operations policy

This policy defines the source-candidate behavior and a proposed operating baseline. It does not establish current AWS, Redis, proxy, backup or capacity configuration.

## Request correlation and diagnostics

- HTTP requests accept a bounded `X-Request-ID` containing only letters, digits, period, underscore or hyphen (maximum 64 characters); malformed or absent values are replaced with a random ID.
- The response echoes the identifier. Application log records inherit the request context. Request log events contain method, registered route template, status and elapsed time only; no query string, body, credentials, user identity or client IP.
- `GET /api/system/metrics` is administrator-only. It reports process-local counts grouped by method, registered route template and HTTP status class, plus mean and maximum request duration. It resets on process restart and is not a durable monitoring or alerting system.
- Metric labels must remain route templates, never raw paths, symbols, account IDs, request IDs or exception text. Keep scraping/alerting outside the public application and alert on sustained conditions rather than each event.

## Dependency failure behavior

- `/api/health` means process liveness only. `/api/ready` checks required database and Redis readiness and returns a sanitized 503 while unavailable. Neither endpoint claims broker readiness.
- Redis/database state unknown means no new exposure. Existing reduce-only risk-reduction paths remain available as their dedicated guards permit.
- Broker timeout, malformed position snapshot or empty-but-unconfirmed state must not be interpreted as a confirmed flat account. Reconcile before resuming new exposure.
- Exercise disk-full, Redis unavailable, database unavailable and broker timeout using isolated fixtures before deployment; record the observed halt, operator recovery and evidence. Never inject these failures against a live account.

## Proposed backup baseline (deployment owner must configure)

1. Take a coordinated encrypted SQLite online backup at least daily, preserving the trade and order-intent journal together; include the runtime-state recovery file according to the reviewed recovery policy.
2. Retain 30 daily and 12 month-end copies in an off-host location with access controls and independent encryption-key custody. Keep Redis backups only for state confirmed as durable; document how ephemeral state is rebuilt.
3. Record UTC creation time, source revision, database integrity result, file checksum, destination and operator. Alert on the *age* of the newest successful copy, not each individual job retry.
4. Monthly, restore a copy into an isolated environment, run SQLite integrity/schema checks, confirm representative audit/trade/order-intent rows, and rehearse reconciliation before allowing the restored engine to accept exposure.
5. Never restore over an active database. Never store backup keys in the repository or alongside the encrypted backup.

This is a proposed cadence. It is not enabled until the operator selects an off-host target, provisions keys, tests retention and records a successful restore drill.

## TLS and capacity gates

- TLS termination, forwarded-header trust, secure cookies, HTTPS/WSS, firewall ports, admin access and the actual broker outbound IP require staging validation against the deployed proxy chain.
- The single-instance scheduler topology and paper-mode container stack are described in ADR-002. Docker build/start, restart with durable volumes and duplicate-scheduler prevention still require an available Docker/staging host.
- No load profile or memory/cost envelope is certified. Measure API and scan latency, websocket clients, ML/RAG peak memory, database growth and headroom on representative hardware before setting a production budget.
