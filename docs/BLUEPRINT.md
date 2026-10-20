# Rebuild implementation blueprint

This document records the scope implemented in this archive. Deployment acceptance remains in STATUS.md and OPERATIONS.md.

## Applications and ownership

| Surface | Purpose | Access |
| --- | --- | --- |
| PUBLIC_APP_ORIGIN | Signal ledger, selected model levels/traces, recorded outcomes, methodology and coarse status | Public read-only |
| ADMIN_APP_ORIGIN | Engine health, signal decisions, paper positions, instrument controls, private Indian-market data, research, Telegram, audit and configuration status | Verified Google identity plus server allowlist |
| dashboard/ | Single editable frontend source, two build targets | Repository |
| AWS backend | FastAPI, scanner, scheduler, paper exchange integration, SQLite and Redis | Private Tunnel origin |
| Cloudflare gateway | Same-origin HTTP, OAuth and WebSocket routing; selects the correct Pages build | Two custom app hostnames |

Canonical initial origins are https://app.vishalkool.top and https://admin-app.vishalkool.top. Root .env supplies configuration. Browser code uses relative paths. Changing origins requires regenerating/deploying gateway config, restarting the backend, and updating DNS/Tunnel and Google's registered redirect URI. Provider bindings cannot change themselves when a local file changes.

## Retained and removed

- Retain existing signal-generation parameters, research safeguards, historical database, Indian-market engine and Telegram capabilities. Add decision traces without changing scoring rules.
- Enforce paper startup, serialized runtime and reconciliation before starting the scheduler.
- Replace customer authentication with Google-only operator access for ADMIN_EMAILS, initially vishalkool166@gmail.com. Verify email, pin Google subject, use opaque hashed sessions, expiry/revocation, Origin checks and CSRF tokens.
- Remove customer signup, password/Resend login, tiers, subscription/payment flows, pricing pages and backend-served frontend. No production billing acknowledgements or renewal emails exist in this noncommercial build.
- Remove browser live-mode switching and destructive Docker purge operations.
- Keep the public PWA. Admin is responsive and does not register a service worker. Auth/API responses are never cached by the new PWA.
- Keep optional SQL-backed private assistant access when its provider is configured. Legacy vector/ML research source is retained without startup activation or automatic model promotion.
- Preserve the existing license position; owner must select a license separately.

## Frontend behavior

Custom warm-paper/charcoal/olive interface with Geist and Outfit typography, compact signal tables, accessible Radix/shadcn-style controls, mobile navigation, explicit focus states, loading/error/empty states, pagination and filters. Public navigation: Overview, Signals, Performance, Methodology, Status. Admin navigation: Overview, Signals, Paper trades, Crypto universe, Indian markets, Research, System health, Telegram, Audit trail, Settings.

Every shipped control connects to an implemented endpoint or navigation action. Missing provider configuration remains unavailable. No seeded trading records, sample profitability, simulated identity or fallback market prices are present in runtime code. Public metrics describe persisted signal outcomes rather than private account returns.

## API and data boundaries

- Public: /api/v1/public/overview, /signals, /signals/{id}, /status and /ws/public.
- Admin: /api/v1/admin/* and /ws/admin require a valid operator session.
- Google: /auth/google, /auth/callback/google, /auth/session, /auth/logout on the admin hostname.
- Telegram: /webhook/telegram on the admin hostname; separate secret, allowed chat/sender, update deduplication and budgets.
- Gateway replaces forged forwarded headers with trusted app host and visitor address, supplies shared origin secret, strips cookies before fetching static Pages assets and preserves WebSocket upgrades.
- Backend rejects unverified origin traffic in production, limits request budgets/body sizes and WebSocket connections, sanitizes public projections and conceals internal failure details.
- Redis is reported through an actual readiness probe; liveness is separate from engine readiness.
- SQLite changes are additive. New identities/sessions do not replace historical records. Empty-install universe initialization uses preserved config and respects all existing rows.
- Account credentials stay in private server/provider settings. Settings API returns configuration presence, never secret values.
- Paper position closing requires a one-use authenticator code; Redis failure denies verification.

## Delivery and acceptance

Ship complete repository source, both prebuilt Pages artifacts, setup/config/backup/authenticator scripts, lockfiles, tests and concise deployment/security/research references. No secrets, databases, node_modules, Git history or GitHub Actions are included. Preserve the existing private .env and database during migration.

Acceptance requires the local checks in STATUS.md plus actual AWS/Cloudflare/Google/Redis/Telegram/exchange/PWA smoke tests. No placeholder configuration can substitute for real provider credentials or certify a deployment that was not executed.
