# Signal Engine 3.0

Signal Engine is a self-hosted market research and trading workspace. It has a public market view and an optional private operator console. It has no customer accounts, SaaS plans, or billing.

## Version 3.0 additions

- **Private Strategy Lab:** four independently versioned research-only candidate
  strategies, simulated replay and shadow evaluations of Binance closed 4h candles.
- **Binance futures context:** public funding, open interest, global and top-account
  positioning ratios. No Hyperliquid connection or wallet-copying assumptions.
- **Groq:** supported GPT-OSS free-tier model configuration with permission-aware
  fallback (`GROQ_API_KEY` required). No new AI vendor subscription.
- **Risk accounting:** signed current Binance Futures equity, stale-equity halt.

See **[Version 3.0 deployment and limitations](docs/UPGRADE_V3.md)** before
upgrading. The original live strategy and exchange safety gates are retained;
new candidate strategies are *not* enabled for actual trading.

## Included

- **Public site:** market context, published signals, outcomes, and methodology.
- **Private console:** Google allowlisted sign-in, live positions, trade journeys, performance, Indian-market monitoring, research assistant, system health, audit, and settings. Responsive visuals use brief motion and respect reduced-motion preferences.
- **Trading service:** Binance USDⓈ-M demo trading by default, with guarded live-mode support that requires server opt-in and TOTP.
- **Telegram:** webhook alerts and focused operator commands, including `/ping`, `/trades`, `/journey`, `/performance`, `/india`, and `/help`.
- **Persistent records:** SQLite trade and signal history, journeys, runtime state, plus the local RAG index. Preserve these during upgrades.

The public and admin interfaces can be hosted separately, together, or individually. Cloudflare is optional. See [Self-hosting](docs/SELF_HOSTING.md) for the complete setup, [Operations and safety](docs/OPERATIONS.md) for backups and trading controls, [Telegram setup](docs/TELEGRAM.md) for bot instructions, and [Research methodology](docs/RESEARCH.md) for strategy and evidence limits.

## Quick start

Use Python 3.12 and Node.js 22. First prepare the environment and leave execution disabled:

```bash
cp .env.example .env
chmod 600 .env
python scripts/setup_env.py
```

Review `.env`, set at least one interface enabled, set its exact origin, and keep `ENGINE_ENABLED=false` and `TRADING_MODE=paper` for initial setup. Then start the backend:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 signal-engine
```

Build the interface(s) you plan to host from `dashboard/`:

```bash
npm ci
npm run build:public
npm run build:admin
```

The public build is `dashboard/dist/public`; the installable operator PWA is `dashboard/dist/admin`. Build only the site(s) you enable. Your static host must provide SPA fallback and proxy `/api/`, `/auth/`, `/ws/`, and `/webhook/` to the backend. See [Self-hosting](docs/SELF_HOSTING.md); Cloudflare Pages and Tunnel instructions are in [Cloudflare hosting](docs/CLOUDFLARE.md).

## Development and checks

```bash
python -m pip install -r requirements-dev.txt
npm --prefix dashboard ci
npm --prefix dashboard run check
npm --prefix dashboard run build
python -m pytest -q tests
npm --prefix dashboard test
```

For local development, run FastAPI on `127.0.0.1:8000`, then use `npm --prefix dashboard run dev` for public or `npm --prefix dashboard run dev:admin` for admin. Configure a local Google OAuth client to test the admin login. Playwright tests use mocked services.

## Operating limits

Paper mode uses Binance's USDⓈ-M demo environment. Live mode can submit real orders and stays unavailable until explicitly enabled on the server. Review [Operations and safety](docs/OPERATIONS.md) before starting the engine or switching modes. Historical performance and research outputs do not guarantee future results.

Licensed under Apache-2.0; see [LICENSE](LICENSE). Service providers, market data, models, and dependencies retain their own terms.
