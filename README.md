# Signal Engine V5

Private-source Python trading engine and React dashboard, distributed in a single repository. **Current handoff is v1.0.0-rc1, a source-level release candidate and not production-certified.** **AWS continues to run the original Python backend at the repository root; Cloudflare Pages builds only `dashboard/`.** The owner intentionally does not use GitHub Actions.

## Layout

| Path | Purpose |
| --- | --- |
| `main.py`, `config.py`, `scheduler.py`, `auth.py` | Existing backend startup, environment and scheduling; paths preserved |
| `agents/`, `engines/`, `trade/`, `api/`, `saas/` | Existing Python trading/API implementation; only targeted pagination and security-email changes |
| `Dockerfile`, `docker-compose.yml` | **Unchanged original AWS deployment contract** |
| `frontend/` | Existing compiled static fallback served by AWS; kept for backwards compatibility |
| `dashboard/` | Editable React/TypeScript source; deploy this folder on Cloudflare Pages |
| `docs/engineering/` | Private engineering blueprint/task ledger, architecture decisions and readiness evidence |
| `docs/operations/` | Two-host rollout and recovery guidance |
| `scripts/verify_local.sh` | Explicit local quality checks; no GitHub Actions |

## Local tests (Python 3.11 target)

```bash
python -m pip install -r requirements.txt
bash scripts/verify_local.sh
```

When npm access is available, `CHECK_FRONTEND=1 bash scripts/verify_local.sh` additionally runs npm clean install, lint, TypeScript checks and production build. Node 22 is recommended for the dashboard. Unit tests do not approve live trading.

## Dashboard local development

```bash
cd dashboard
cp .env.example .env.local
npm ci
npm run dev
```

Vite proxies API/auth/WebSocket requests to `http://127.0.0.1:8000` for local development unless an override is explicitly supplied. Production Cloudflare builds must set `VITE_API_URL` and `VITE_WS_URL` to the live **AWS HTTPS/WSS** origin; these are public URLs, never secrets.

## Hosting / existing GitHub repo

Keep **`vishalkool166/crypto-engine`** as your canonical repository and retain its Git history. Cloudflare Pages connects to that Git repository with root `dashboard`, command `npm run build`, output `dist`, and Node 22. AWS stays on its existing root-level Dockerfile and Compose config; the current automatic AWS update mechanism must be identified before merging into production. See [controlled migration playbook](docs/operations/AWS_CLOUDFLARE_ROLLOUT.md).

Existing GitHub Actions workflows are intentionally removed. Cloudflare's native Git integration builds frontend commits independently; it does not redeploy your Python engine.

## Security and release status

- Existing trade algorithms and live/paper mode controls are not rewritten; **do not enable real capital on the basis of these code changes**.
- Resend is an **inactive** provider adapter reserved exclusively for account verification/recovery/security emails. Password reset workflows remain unfinished; do **not** activate email without token, cooldown, session revocation and security review.
- Telegram is the trading alert channel; no trade/market/performance email functionality is implemented.
- Credentials, live SQLite volumes, Redis data and exchange secrets must never enter Git.
- Local 161 Python regressions pass with 1 auth-dependent module skipped in the isolated environment. Frontend syntax parses, but npm clean build, AWS deployment, live Redis, browser auth and broker recovery still require external verification. See [readiness report](docs/engineering/RELEASE_EVIDENCE.md).

The historical signal-strategy documentation remains in `docs/`; engineering planning docs are not included in the Cloudflare static build. This repository is private by default. No copyright license is granted by inclusion in this archive.

## Release gates and change safety

- See [v1.0.0 candidate verification](docs/engineering/RELEASE_EVIDENCE.md), [machine-readable gates](docs/engineering/RELEASE_GATES_V1.json), [security policy](SECURITY.md), and [contribution workflow](CONTRIBUTING.md).
- `scripts/restore_sqlite.py` restores an integrity-checked snapshot into a **new file only**. It must never be aimed at a running production database.
- A Cloudflare Pages build requires public `VITE_API_URL` (HTTPS) and `VITE_WS_URL` (WSS) at build time; `dashboard/scripts/check-deploy-env.mjs` validates them. Use a same-site custom domain for auth tests.
- `STRICT_SESSION_ORIGIN_CHECK=false` is an explicit deployment compatibility guard. Enable only after staging confirms cookie-origin compatibility; it is not automatically safe to switch on at an untested EC2 instance.
