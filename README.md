# Signal Engine

Self-hosted market intelligence, strategy research, and risk-governed Binance USDⓈ-M trading. Signal Engine combines four independent crypto strategy evaluators, one portfolio-level execution pipeline, a public research website, and a private operator console.

> **Release 3.4 · Source distribution.** This release has passed focused automated checks, but has **not** passed a complete production frontend build or authenticated exchange demonstration in the packaging environment. No strategy has a certified profitable edge. See [Verification](docs/VALIDATION.md) before deployment.

## Capabilities

| Area | Included |
| --- | --- |
| Strategy engine | Trend continuation, breakout/retest, range reversion, momentum reversal; shared closed-candle features and per-strategy evidence |
| Execution | Binance demo and explicitly gated live mode, order-intent journal, portfolio risk checks, stop/target proposals, reconciliation |
| Research | Reproducible strategy experiments, walk-forward tools, comparison and decision history; historical results are not certified |
| Operations | Coin-scan status, signal expiry, system health, infrastructure telemetry when accessible, Telegram alerts |
| Interfaces | Public methodology and signal outcomes; Google-authenticated admin, interactive Trade Journey and strategy controls |
| AI | Optional Groq-assisted research with retrieval; no autonomous LLM order placement |

The four strategies evaluate independently within the same scan. The shared arbitrator selects at most one eligible proposal per symbol and rejects opposing directions. A proposal does **not** bypass risk limits, account mode, or the exchange executor. [Architecture](docs/ARCHITECTURE.md) · [Strategy mechanics](docs/STRATEGIES.md)

## Requirements

- Docker Engine with the Compose plugin and writable persistent application storage.
- Node.js 22 and npm to build the React/Vite public and admin interfaces.
- Python 3.12 for local backend development and verification (the Docker image includes Python).
- Your **existing** Binance credentials for authenticated demo operation; Google OAuth only when hosting admin. Redis runs through Compose. Groq and Telegram are optional for their respective features.

No new mandatory environment variables or provider accounts were added in 3.4. Existing deployments should **retain** `.env`, `database/`, state files, and persistent volumes.

## Quick start

Start with the engine disabled and paper mode selected. Never commit `.env`.

```bash
python scripts/setup_env.py
chmod 600 .env
# Configure production origins and provider credentials in the generated .env.
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

`scripts/setup_env.py` creates fresh application secrets and refuses to overwrite an existing `.env`. If Python is unavailable on the host, copy `.env.example` to `.env` and create unique strong secrets manually. Configure production origins and authentication before exposing the service.

Build the frontend from `dashboard/` on a host with npm registry access:

```bash
cd dashboard
npm ci
npm run check
npm run build
```

Build outputs are `dashboard/dist/public` and `dashboard/dist/admin`; both require the reverse proxy/API routing described in [Deployment](docs/SELF_HOSTING.md). Running Docker alone **does not** publish the interfaces. `docker-compose.cloudflare.yml` is an optional overlay; base Compose does not require a tunnel token. Cloudflare is optional; see [Cloudflare setup](docs/CLOUDFLARE.md).

## Operating and development guides

| Need | Documentation |
| --- | --- |
| Install, update, host the interfaces | [Deployment](docs/SELF_HOSTING.md) |
| Backups, restart, modes, risk controls | [Operator runbook](docs/OPERATIONS.md) |
| Architecture, ownership and data flow | [Architecture](docs/ARCHITECTURE.md) |
| Strategy decisions, invalidation, exit hypotheses | [Strategies](docs/STRATEGIES.md) |
| Environment variables and configuration | [Configuration](docs/CONFIGURATION.md) and [`.env.example`](.env.example) |
| API boundaries and authentication | [HTTP API](docs/API.md) |
| Research methodology and evidence limitations | [Research](docs/RESEARCH.md) |
| Tests, known verification gaps | [Testing](docs/TESTING.md) and [Validation](docs/VALIDATION.md) |
| Telegram commands | [Telegram](docs/TELEGRAM.md) |
| Changes in this release | [Changelog](CHANGELOG.md) |

## Contributing and security

Source contributions are welcome: consult [Contributing](CONTRIBUTING.md) for development conventions and review expectations. Report vulnerabilities privately using the guidance in [Security](SECURITY.md); do not put secrets or exploit details in a public issue. [Code of conduct](CODE_OF_CONDUCT.md).

**Risk notice.** Trading futures can cause substantial losses. Structural price targets and risk/reward checks are estimates, not price forecasts or guarantees. A clean source checkout does not authorize live trading; the separately guarded live switch can submit real orders if explicitly configured and enabled. Read [Operations](docs/OPERATIONS.md) before enabling the scanner or switching modes.

Source integrity: after extracting a release archive, run `python scripts/verify_manifest.py` to check included files against [SHA256SUMS](SHA256SUMS). The manifest detects accidental changes to the distributed archive; it is **not** a signature or proof of publisher identity.

Licensed under [Apache License 2.0](LICENSE). Exchange, AI, infrastructure and package providers apply their own terms.
