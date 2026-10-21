# Release notes — 2.1.0

Prepared 21 October 2026.

## Interface

Rebuilt the public and operator layouts using a neutral finance-dashboard
composition informed by the supplied Shadcn UI Kit reference. Added individual
metric cards, interactive ledger charts, outcome distribution, inset admin canvas,
grouped navigation, page search, mobile focus-managed navigation, and consistent
Radix/shadcn-style controls. All existing admin routes remain available, including
Performance, Trades & journey, research, Indian markets, telemetry, stored data,
Telegram, settings, and audit.

Replaced the accumulated theme overrides with complete semantic light/dark
palettes. A CSP-compatible blocking theme script avoids the initial theme flash.
Both themes are tested at 320, 390, 768, and 1440 pixels. Motion is restrained and
respects reduced-motion preferences. Runtime charts use persisted records only.

## Execution

Added Google-session/CSRF/TOTP-protected paper/live switching with explicit typed
confirmation, Redis replay protection, attempt budgets, active-operation guards,
local/journal checks, both-account preflight, mandatory audit, durable selection,
and graceful restart. Active account clients never hot-swap credentials.

New trades retain their execution mode. Existing records remain intact and are
labelled legacy. Runtime sizing calculations and delayed closed-trade exchange
synchronization are partitioned by environment. Fixed canonical database-path
handling in the order journal and a dormant exception-variable typo.

## Telegram

Polling is now the default inbound transport. It starts independently of exchange
readiness and uses a single-consumer Redis lease. Stale webhooks are removed
without dropping pending updates. Added actual `/start` and `/ping` handlers,
transport/rejection diagnostics, corrected dependency health reporting, and
active-environment labels. Existing message emoji and readable formatting remain.
Webhook mode remains available for deployments that prefer it.

## Self hosting

The tunnel starts independently from the application health gate, uses HTTP/2 by
default, and uses automatic container restarts. Added a host-boot systemd unit,
upgrade guide, execution guide, revised Telegram instructions, and environment
examples. Public and private Pages builds and same-origin proxy boundaries remain.

## Verification

See [docs/STATUS.md](docs/STATUS.md) for executed checks and external integration
limits. No real exchange order, live activation, production deployment, or
user-account Telegram message was performed during development.
