# Release verification

Rebuild candidate: 2026-10-20. Production deployment is pending account-side configuration and acceptance checks.

## Verified locally

| Check | Result |
| --- | --- |
| Python regression/security tests | 155 passed |
| Gateway authorization/routing tests | 5 passed |
| Browser contract tests | 5 passed |
| TypeScript and two production builds | Passed |
| Worker bundle dry run | Passed; no deployment performed |
| Browser sweep against local backend | All 5 public views, Google login view, 10 authenticated admin views rendered; no uncaught page errors |
| Responsive visual inspection | Public/admin desktop and 390px mobile; no page overflow on inspected routes |
| Python, frontend and gateway dependency audits | No known advisories in installed versions at verification time |
| Retired frontend and host | Removed; dashboard/ is the only frontend source |

Browser contract tests use isolated API fixtures. The separate local-backend sweep used a disposable empty database, local test-only operator session, disabled scheduler, and blocked external sockets. It did not authenticate against Google or connect to a broker. A genuinely empty installation now initializes the preserved 18-instrument configuration; it creates no signals/trades and never re-enables existing disabled rows.

Redis was not running in the local browser environment: the admin console correctly reported disconnected from its actual probe. The regression suite covers connected, failed and unknown health behavior. Compose supplies the private Redis service; production connectivity must be checked after startup.

## External checks still required

- Build/start containers on the target AWS host; Docker daemon was unavailable here.
- Configure both Pages projects, Tunnel DNS and Worker Routes; verify HTTP and WebSocket upgrades through Cloudflare.
- Complete real Google sign-in with the allowlisted account; test a denied account and logout.
- Confirm the existing database backup, permissions, migration and restore on a test instance.
- Verify actual Redis, Telegram delivery, Binance demo reconciliation, partial fills and restart recovery. Angel One remains a private optional integration.
- Install/update the public PWA on a real mobile device, including migration from the prior service worker.
- Set Cloudflare rate/WAF rules and review operational denials and provider limits.

## Strategy status

Paper-only. No live activation or parameter promotion. The original per-coin strategy settings are preserved. Complete OHLCV/funding data and walk-forward experiments were not supplied or rerun; profitability and a winning-trade rate are not certified. Historical records are retained; their execution provenance is not inferred from the current paper runtime.

No remote GitHub repository was modified or production service deployed in this handoff. See OPERATIONS.md for source replacement, provider configuration, smoke checks and rollback.
