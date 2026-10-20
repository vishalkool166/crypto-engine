# Signal Engine

Signal Engine is a market-analysis and trading research application with crypto and Indian-market signal workflows, risk controls, a Python API, and a React dashboard.

**Research software; not approved for live-money deployment.** Trading can lose money. Profitability and production execution have not been independently validated. Keep trading in paper mode until the acceptance requirements in [Engineering status](docs/STATUS.md) are complete.

## Project layout

| Path | Purpose |
| --- | --- |
| `main.py`, `api/` | FastAPI service and API routes |
| `agents/`, `engines/` | Signal analysis, scoring, risk, and sizing |
| `trade/` | Exchange adapters, order controls, and reconciliation |
| `backtest/`, `data/`, `ml/` | Research, market history, outcomes, and evaluation |
| `saas/` | Accounts, access tiers, and administration |
| `dashboard/` | Editable React, TypeScript, and Vite source |
| `dashboard/dist/` | Cloudflare Pages build output |
| `frontend/` | Existing static path served by the backend |
| `docs/` | Architecture, operations, integrations, and research status |

## Run locally

Install backend dependencies and configure a local `.env` using the variables consumed by `config.py` and `docker-compose.yml`. Never commit credentials.

```bash
python -m pip install -r requirements.txt
python main.py
```

Run the dashboard from its existing directory:

```bash
cd dashboard
npm ci
npm run dev
```

The production dashboard uses the browser's current origin for API, authentication, and WebSocket requests. The Vite development proxy targets `https://app.vishalkool.top`. The production edge must forward `/api/*`, `/auth/*`, and `/ws/*` to the backend.

## Cloudflare Pages

Set the Pages project root to `dashboard`, the build command to `npm ci && npm run build`, and the output directory to `dist`. Build files stay under `dashboard/dist/`. The backend's existing root `frontend/` directory remains available for its static fallback route.

## Verify

```bash
python -m pytest -q tests
python -m compileall -q -x 'frontend/' .
cd dashboard && npm run lint && npm run build
```

See [Architecture](docs/ARCHITECTURE.md), [Operations](docs/OPERATIONS.md), [Research](docs/RESEARCH.md), and [Engineering status](docs/STATUS.md) for system boundaries, deployment precautions, and known validation limits.

## Scope and licensing

Twitter post creation and approval commands have been removed. Telegram market briefings remain. Resend is intended for account setup and security messages only. Stripe checkout is not implemented in this source bundle; paid subscriptions must remain unavailable until checkout, webhooks, and entitlement updates are built and tested.

No open-source license is included. All rights are reserved until the repository owner selects a license.
