# Signal Engine

Signal Engine has a public market research site and a private operator console. The browser source lives in `dashboard/`; both Cloudflare Pages projects build from that directory.

| Site | Purpose |
| --- | --- |
| `app.vishalkool.top` | Public signal records, performance history, methodology, and service status |
| `admin-app.vishalkool.top` | Google-authenticated operator access to paper trading, engine health, markets, research, Telegram, audit, and settings |

FastAPI runs in Docker on AWS and is reached through Cloudflare Tunnel. Redis and SQLite remain private to the Docker network. The application is paper-only. It has no customer signup, subscriptions, or payment flow.

## Start here

- [Deployment guide](DEPLOY.md): Pages, Tunnel, OAuth, environment, and release checks.
- [Security model](docs/SECURITY.md)
- [Research methodology](docs/RESEARCH.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Verification record](docs/STATUS.md)

## Local development

Use Python 3.12 and Node 22. From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
npm --prefix dashboard ci
ENV=development ENGINE_ENABLED=false uvicorn main:app --host 127.0.0.1 --port 8000
```

In separate terminals run `npm --prefix dashboard run dev` and `npm --prefix dashboard run dev:admin`. The Vite servers proxy API, auth, WebSocket, and webhook requests to the local FastAPI service.

Build and verify both Pages outputs with:

```bash
npm --prefix dashboard run build
python -m pytest -q tests
npm --prefix dashboard test
```

The public and admin builds are written to `dashboard/dist/public` and `dashboard/dist/admin`. The repository archive contains source only; Pages creates these build outputs.

## Important operating limits

- `TRADING_MODE` must remain `paper`.
- A paper scheduler starts only after demo credentials load and existing exchange state reconciles cleanly.
- Redis health in the console reflects the actual backend probe.
- Profitability has not been established. Signal grades are rule-based scores, not calibrated probabilities.
- No license is included. Choose one before presenting the project as licensed open source.
