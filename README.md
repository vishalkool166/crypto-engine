# Signal Engine

**Signal Engine** is a cryptocurrency market research and paper-trading service with a React dashboard. The Python service runs on AWS; the dashboard is built from `dashboard/` for Cloudflare Pages.

> **Release status: engineering candidate.** This repository snapshot is not the deployed AWS revision and is not certified for production or live trading. Signal quality has not been evaluated on the required approved out-of-sample dataset. Keep trading in paper mode.

## What it contains

- Market scanning, signal scoring, research and backtesting tools.
- FastAPI endpoints, Telegram alerts, authentication and account controls.
- Order journaling, reconciliation and fail-closed trading controls.
- React/Vite dashboard for user and administrator workflows.
- Local verification scripts, regression tests and operations guidance.

The backend remains the system of record for the scheduler, exchange connections, Redis, and persistent SQLite state. The frontend is an independently built client. No GitHub Actions workflows are used.

## Repository layout

| Path | Purpose |
| --- | --- |
| `main.py`, `scheduler.py`, `config.py` | AWS application entrypoint, jobs and configuration |
| `agents/`, `engines/`, `trade/`, `api/`, `saas/` | Analysis, execution controls, API and accounts |
| `dashboard/` | Cloudflare Pages React/Vite application |
| `tests/` | Python regression and security tests |
| `scripts/` | Local checks, audits and SQLite backup/restore tools |
| `docs/` | Architecture, operations, research and release status |

## Local development

Use Python 3.11 and Node 22. Work in an isolated environment with synthetic or paper credentials. Never point a local checkout at production databases or exchange credentials.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-test.txt
python -m pytest -q
```

Run frontend checks from `dashboard/`:

```bash
npm ci
npm run lint
npx tsc -b
npm run build
```

Run repository checks from the root:

```bash
bash scripts/verify_local.sh
python scripts/release_audit.py --output /tmp/signal-engine-release-audit.json
python scripts/freeze_strategy_baseline.py --check
```

Cloudflare production builds require the public `VITE_API_URL` and `VITE_WS_URL` values. Do not put secrets in frontend variables.

## Deployment boundaries

- **AWS:** preserves the existing Compose service, `uvicorn main:app` entrypoint, scheduler, Redis service and `/app/database` volume contract. Confirm the deployed revision and automatic update mechanism before any change.
- **Cloudflare Pages:** use repository `vishalkool166/crypto-engine`, root `dashboard`, build command `npm run build`, output directory `dist`, and Node 22.
- **Authentication:** Google OAuth remains backend-managed. Email/password accounts are present in source but disabled by default pending staging verification. Resend is exclusively for account setup and security communications; Telegram remains the trading-alert channel.

See [Configuration](docs/CONFIGURATION.md) for environment variables, [Operations](docs/OPERATIONS.md) before staging or deployment, [Release status](docs/engineering/RELEASE_EVIDENCE.md) for current evidence and blockers, and [Research](docs/RESEARCH.md) for the signal-evaluation protocol.

## Safety and scope

Paper mode is the expected operating mode. A successful unit test, frontend build, or health response does not establish production readiness, safe exchange execution, or profitability. Never deploy this archive over a live checkout, change production data volumes, or enable live orders without a reviewed backup, staging rehearsal, rollback plan and explicit operator approval.

The project intentionally has no GitHub Actions. See [Contributing](CONTRIBUTING.md) and [Security](SECURITY.md) before proposing changes.
