# Signal Engine 2.1

Signal Engine is a self-hosted market research and trading application. It has a public read-only site and a private, Google-authenticated operator console. The application intentionally has no customer accounts, SaaS plans, or billing.

## What is included

| Area | What it provides |
| --- | --- |
| Public site | Published signals, market context, methodology, and public service status. It does not expose private account, position, or monetary performance data. |
| Admin console | Google-only operator access to the engine, trades, trade journeys, performance, research, Telegram, audit and stored database records. |
| Engine | Existing strategy, exchange reconciliation, order management, risk controls and scheduled scans. It starts disabled until configured. |
| Telegram | Outbound signal alerts plus allowlisted private operator commands through outbound polling by default, with an optional webhook transport. |
| Storage | SQLite application database and Redis coordination store. Existing SQLite files must be retained during upgrades. |

The admin console includes a **Stored data** view for inspecting application tables. Secret-like fields are masked there. SaaS-era records remain in the database and are not deleted by this release; customer billing and signup are not part of the product.

## What changed in 2.1

- Public and admin finance-dashboard layouts with a consistent neutral shadcn/Radix component system.
- One semantic palette per theme, a blocking theme initialization script, and mobile navigation with focus management.
- Interactive ledger charts, individual metric cards, and retained Performance and Trade Journey pages.
- TOTP-confirmed paper/live switching through a verified account transition and a fresh engine process.
- Telegram polling starts independently of the trading scheduler, with `/start`, `/ping`, and visible inbound diagnostics.
- Independent Cloudflare Tunnel startup, HTTP/2 by default, automatic container restart, and an optional systemd unit.

**Existing installation:** start with [docs/UPGRADE_2_1.md](docs/UPGRADE_2_1.md).

## Start here

1. Read [DEPLOY.md](DEPLOY.md) for the full self-host and Cloudflare setup.
2. Read [docs/OPERATIONS.md](docs/OPERATIONS.md) before enabling the paper engine.
3. Copy [.env.example](.env.example) to `.env` and fill only the values needed for your deployment.
4. Configure Telegram using [docs/TELEGRAM.md](docs/TELEGRAM.md).
5. Use [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md) for the operator console and [docs/DATA.md](docs/DATA.md) for stored records and backups.
6. Review [docs/SECURITY.md](docs/SECURITY.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and [docs/RESEARCH.md](docs/RESEARCH.md).

## Local development

Use Python 3.12 and Node.js 22. From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
npm --prefix dashboard ci
ENV=development \
PUBLIC_APP_ORIGIN=http://localhost:5173 \
ADMIN_APP_ORIGIN=http://localhost:5174 \
ENGINE_ENABLED=false \
TRADING_MODE=paper \
uvicorn main:app --host 127.0.0.1 --port 8000
```

In separate terminals, run the two Vite apps:

```bash
npm --prefix dashboard run dev
npm --prefix dashboard run dev:admin
```

The public site is at `http://localhost:5173`; the admin site is at `http://localhost:5174`. To complete a local Google sign-in, configure a Google OAuth client with `http://localhost:5174/auth/callback/google`, then add its credentials and your email to `.env`. The Playwright tests use mocked operator APIs.

## Build and verification

```bash
npm --prefix dashboard run build
python -m pytest -q tests
npm --prefix dashboard exec -- playwright install chromium
npm --prefix dashboard test
```

The two Pages outputs are `dashboard/dist/public` and `dashboard/dist/admin`. Cloudflare Pages must deploy the repository `dashboard/functions/` directory for API/auth/webhook proxying; a static-only upload is incomplete.

## Operating boundaries

- Paper is the initial default. Live activation requires server opt-in, configured live credentials, TOTP, flat-account checks, and a managed restart. See [docs/EXECUTION_MODES.md](docs/EXECUTION_MODES.md).
- `ENGINE_ENABLED=false` is the safe first boot. Enable only after the database is backed up, demo credentials are valid, and reconciliation is healthy.
- Redis is required for authenticated sessions, request limits, scheduler coordination, and Telegram command deduplication.
- A scan alert proves outbound Telegram delivery only. Use the setup checks in [docs/TELEGRAM.md](docs/TELEGRAM.md) to verify inbound commands.
- Strategy grades are rule-based scores. Historical results do not establish future profitability.
- No license is included. Select a license before redistributing the repository as open source.
