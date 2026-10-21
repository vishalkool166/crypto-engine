# Release notes — 1.0.0

Prepared 2026-10-21.

## Release scope

This build keeps the public market research experience and the private Google-only admin console. SaaS registration, customer access, subscriptions, and billing are intentionally absent. Runtime configuration and operator access are server-side.

## Admin and persisted data

- Restored the admin Performance page with persisted metrics, grade/instrument/version/regime breakdowns, descriptive factor scores, and recent signal history. Backtests remain available from Research.
- Restored Trade Journey charts in open and closed paper-trade views, with entry/stop/target/exit context where snapshots exist.
- Added a private read-only SQLite table browser with pagination, search, CSV export, and secret-like column redaction.
- Expanded System Health to show rejection statistics, engine diagnostics, relative-strength ranking, decision traces, and filter analysis.
- Kept historical account and plan tables in the database for review; startup does not purge them.
- Fixed theme preference initialization and shared light/dark semantic token behavior.

## Telegram and paper exchange

- Preserved emoji and readable spacing in Telegram messages while HTML-escaping dynamic message text.
- Added `/journey <trade_id>` to the inbound command router and registered it with Telegram.
- Improved trade and position summaries with clear paper labels, direction, grade, entry, observed P&L, stop/target and health context.
- Added allowed-sender, webhook destination and command-registration diagnostics to the admin Telegram page.
- Updated the default USDⓈ-M Futures demo REST and WebSocket endpoints to Binance's current documented hosts.

## Self-hosting and operations

- Replaced brief deployment notes with host setup, database preservation, environment variables, Google OAuth, Cloudflare Tunnel, Pages build settings, acceptance checks, upgrades, backups and rollback guidance.
- Added operator, data-retention and Telegram setup guides.
- Replaced personal example emails/domains in runtime defaults with local/example placeholders.
- Added the dashboard Node.js version pin (`dashboard/.nvmrc`).

## Verification

- Backend suite: 163 passed.
- `npm run build`: TypeScript check and public/admin builds passed.
- Pages proxy tests: 5 passed.
- Browser suite: not completed because Chromium was unavailable and its download was truncated in the build environment. See [docs/STATUS.md](docs/STATUS.md).
- Cloudflare/AWS production integrations still require deployment-specific verification.
