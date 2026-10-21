# Release verification

## Verified locally

| Check | Result |
| --- | --- |
| Backend regression and security suite | 155 passed |
| TypeScript and public/admin Vite builds | Passed |
| Browser UI tests | 6 passed, including Google login entry, API error states, mobile navigation, and theme persistence |
| Pages proxy tests | 5 passed, covering routing scope, trusted headers, public/admin isolation, OAuth cookies, and bidirectional WebSocket relay |
| npm dependency audit | 0 reported vulnerabilities |
| Visual review | Public overview, admin overview, and Google sign-in inspected at desktop widths; mobile public navigation tested without horizontal overflow |
| Source archive hygiene | Excludes `.env`, databases, `frontend/`, node_modules, virtual environments, `dist/`, and generated artifacts |

Pages routing and WebSocket behavior were checked against Cloudflare’s published documentation. The Pages Functions have local unit tests, but have not been deployed to a Cloudflare account or tested through an active Tunnel.

## Production checks still required

- Configure both Pages projects, custom domains, production variables/secrets, and Tunnel routing.
- Build and start the Docker Compose service on the AWS host with the preserved database volume and UID 10001 permissions.
- Complete real Google sign-in with the allowlisted account and confirm another account is denied.
- Verify the real Redis probe, demo exchange authentication and reconciliation, Telegram webhook, and PWA installation on a phone.
- Confirm backup and restore on a test database, then review Cloudflare WAF/rate limits and deployment logs.

## Strategy status

The system is paper-only. No live activation or strategy parameter changes are included. Historical profitability has not been established or represented as a guaranteed result. Existing records do not by themselves prove that a signal was executable or profitable.

## Scope of this handoff

This source correction keeps the existing signal engine, SQLite data model, and Google-only operator design. It removes the previous standalone gateway Worker in favor of path-scoped Pages Functions. The two Pages projects need server-side `APP_TARGET`, `BACKEND_ORIGIN`, and `ORIGIN_PROXY_SECRET` configuration; exact values are in [DEPLOY.md](../DEPLOY.md).
