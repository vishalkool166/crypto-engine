# Signal Engine

Market research and paper-trading operations with two distinct applications:

| Application | Purpose |
| --- | --- |
| https://app.vishalkool.top | Public signal ledger, methodology, recorded outcomes, and service status |
| https://admin-app.vishalkool.top | Google-authenticated operator console, private paper trades, system health, markets, research, Telegram, audit, and settings |

The frontend source is entirely in **dashboard/**. The Python backend stays on AWS. Cloudflare Pages hosts the two static builds; a small Worker routes each hostname to the appropriate Pages build or to the AWS service through Cloudflare Tunnel.

**Operating mode: paper only. Strategy profitability: not evaluated.** Grades are rule-based scores, not calibrated win probabilities. No customer accounts, subscriptions, billing, or live-mode switches are exposed.

## Release status

See **docs/STATUS.md** for exact verification evidence and remaining deployment checks. The downloadable archive contains source and separate prebuilt public/admin assets. It does not contain production credentials, a database, or a trained model.

Start with **docs/OPERATIONS.md** to replace the current repository and configure Pages, Google, AWS, Tunnel, and the gateway. Source replacement alone does not deploy the external configuration.

## Development

Requires Python 3.12 and Node 22.12+. Local verification used Python 3.12 and Node 24.19; Pages is configured for Node 22.

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
npm --prefix dashboard ci
ENV=development ENGINE_ENABLED=false uvicorn main:app --host 127.0.0.1 --port 8000
npm --prefix dashboard run dev
npm --prefix dashboard run dev:admin
~~~

The public dev server uses port 5173; admin uses 5174. API/WebSocket requests are proxied to the local backend. Google OAuth requires an exact registered callback and configured credentials; there is no development login bypass.

~~~bash
python -m pytest -q tests
npm --prefix dashboard run build
npx --prefix dashboard playwright install chromium
npm --prefix dashboard test
npm --prefix deploy/cloudflare ci
npm --prefix deploy/cloudflare test
~~~

## Source map

- **main.py, operator_auth.py, portal_settings.py:** HTTP boundaries, Google operator identity, revocable hashed sessions, and canonical domain configuration.
- **api/portal.py:** Explicit public signal projection and private operational endpoints.
- **agents/, engines/, trade/:** Existing strategy, sizing, execution safeguards, and order journal.
- **alerts/telegram/:** Operator-only commands, reporting, webhook validation, deduplication, and rate limits.
- **backtest/:** Historical research and fail-closed evidence assessment.
- **dashboard/:** Public/admin React builds, local shadcn-style UI primitives, and the public PWA.
- **deploy/cloudflare/:** Gateway Worker and its tests.
- **scripts/:** Private environment setup, deployment-config generation, and online SQLite backup.

Historical customer tables remain in existing databases to avoid destructive migration. They have no customer-facing routes or billing workflow. Vector-retrieval and ML research source is preserved but is not part of the active strategy. The private assistant uses bounded SQL retrieval and requires explicit Groq configuration.

## Technical references

- [Architecture](docs/ARCHITECTURE.md)
- [Deployment, migration, and rollback](docs/OPERATIONS.md)
- [Security](docs/SECURITY.md)
- [Research methodology](docs/RESEARCH.md)
- [Blueprint and scope](docs/BLUEPRINT.md)
- [Verification status](docs/STATUS.md)

No license has been selected by the repository owner. This release does not add a license or change ownership rights.
