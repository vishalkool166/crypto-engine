# Signal Engine

A Python market-signal and paper-trading service with a React dashboard. This repository contains **one AWS backend** and **one Cloudflare Pages frontend**. The trading scheduler, exchange integrations, Redis and persistent SQLite state remain on AWS.

> **Release state:** Phases 01–09 cumulative **source candidate**. This checkout is not the running EC2 revision. Offline tests and static checks do not certify a production deployment, live execution, or any profitable trading edge. Email/password signup remains disabled until all staging security gates pass.

## Repository map

| Location | Responsibility |
| --- | --- |
| `main.py`, `scheduler.py`, `config.py`, `auth.py`, `database.py` | Existing AWS application entrypoints and runtime configuration |
| `agents/`, `engines/`, `trade/`, `api/`, `saas/` | Market analysis, execution controls, API endpoints, user access and plan rules |
| `dashboard/` | Editable React/Vite application deployed to Cloudflare Pages |
| `tests/` | Python regression and security tests |
| `scripts/` | Offline validation, SQLite backup/restore and release checks |
| `docs/ARCHITECTURE.md`, `docs/OPERATIONS.md` | System boundaries and operational controls |
| `docs/engineering/MASTER_TASK_LEDGER.csv` | Tracked engineering tasks and remaining release gates |

The obsolete compiled AWS `frontend/` directory is intentionally absent. Browser entrypoints on AWS redirect to the configured Cloudflare frontend; the backend continues to serve API, Google OAuth, WebSocket and Telegram webhook endpoints.

## Running and testing locally

Python **3.11** and Node **22** are the intended development runtimes. Use an isolated environment and *never* run this checkout with production credentials or a production trading database.

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-test.txt
python -m pytest -q
python scripts/check_monorepo_contract.py
python scripts/check_task_ledger.py
```

Frontend development and checks:

```bash
cd dashboard
npm ci
npm run lint
npx tsc --noEmit -p tsconfig.app.json
npm run build
```

Local frontend development can use `npm run dev` and the Vite localhost API proxy. The Cloudflare production build requires `VITE_API_URL` and `VITE_WS_URL`, both **public** URLs (never credentials).

## Deployments

- **AWS EC2:** Existing Compose service `signal-engine`, `uvicorn main:app`, root `Dockerfile`, `/app/database` bind mount and `redis_data` volume are preserved. Redis remains private to Compose. The current Git-to-AWS update mechanism is external to this repository and must be verified separately.
- **Cloudflare Pages:** Connect `vishalkool166/crypto-engine`; root `dashboard`; `npm run build`; output `dist`; Node 22. Git integration does not require GitHub Actions.
- **Current frontend:** `https://app.vishalkool.top`. **Current API:** `https://signal-engine-v5.vishalkool.top`. These hostnames must not be exchanged without a reviewed OAuth/DNS cutover.
- **Google login:** AWS performs the OAuth callback, sets its backend-scoped session cookie and redirects to `FRONTEND_URL`. Verify cookie/CORS behavior against both domains after any change.
- **Health checks:** `GET /api/health` is public liveness-only (used by Docker). `GET /api/system/health` is administrator-only diagnostics and includes an actual Redis ping result. A failed health query is not proof of Redis failure.

See [operations](docs/OPERATIONS.md) for backup, scheduler, and incident response. **Do not copy a candidate ZIP straight into a live auto-deploy checkout without backup and staging verification.**

## Accounts and plans

Google Sign-In remains the deployed login. A separate email/password registration, verification, sign-in and recovery implementation is included in source but **disabled by default** pending browser, Resend and session-security verification. Set neither email feature flag on AWS yet. Resend is exclusively for account verification and security messages, never signals, trades, reports or marketing; Telegram remains the trading-alert channel.

This candidate adds three **new** account tables through `database.init_db()`; it does not modify existing User or Subscription schemas. See [release evidence](docs/engineering/RELEASE_EVIDENCE.md) before any staging activation.

`config.py` is the current authority for entitlements. `GET /api/pricing` exposes its plan catalogue to the dashboard, including Free/Pro/Elite signal visibility and restrictions. Billing and customer self-upgrades are **not** enabled; administrator changes require authorization. Never infer live-trading permission from a subscription tier.

## Status and safety

This release has isolated Python tests for account provisioning, email verification/reset, tier changes, privilege checks, health-route contracts, exchange outages, logout routing, and per-tier WebSocket updates. It still needs a full browser build, real Redis probe, end-to-end OAuth tests, safe AWS image rebuild, recovery drill and independent trading review. See [verification evidence](docs/engineering/RELEASE_EVIDENCE.md) and [engineering ledger](docs/engineering/MASTER_TASK_LEDGER.csv).

The project intentionally does not use GitHub Actions. Do not commit `.env`, exchange keys, Redis snapshots or trading databases.

## Manual release assessment

The repository has no GitHub Actions. On a separate development machine with the required runtimes:

```bash
bash scripts/verify_local.sh
python scripts/release_audit.py --output /tmp/signal-engine-release-audit.json
python scripts/freeze_strategy_baseline.py --check
```

The release audit explicitly leaves browser, real Redis, AWS rollout, email provider, and exchange testnet gates **blocked** until someone performs and records them. A skipped test is not counted as a completed verification gate. The `S0` strategy manifest verifies *source identity*, not signal profitability; quantitative evaluation uses [`docs/RESEARCH.md`](docs/RESEARCH.md).

To deploy, compare this candidate against the running AWS commit first, test with a restored **staging** database and isolated Redis, and follow the rollback procedure in [`docs/OPERATIONS.md`](docs/OPERATIONS.md). Never copy a ZIP over the production SQLite database or use an unverified auto-deployment to `main`.
