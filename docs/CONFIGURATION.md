# Configuration reference

Copy `.env.example` only for a disposable local environment. Supply real credentials through a secret manager; never commit them or paste them into `VITE_*` variables. The example file contains placeholders and safe local defaults, not a production configuration.

## Core runtime

| Variable | Purpose | Safe starting value |
| --- | --- | --- |
| `ENV` | Runtime environment label | `development` |
| `PORT` | FastAPI listen port | `8000` |
| `DOMAIN` | Public backend URL used for callback/webhook URLs | Blank locally; set to the reviewed API origin in staging |
| `FRONTEND_URL` | Browser origin used for redirects | `http://localhost:5173` locally |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` locally |
| `SIGNAL_ENGINE_DATABASE_PATH` | Application SQLite database path | `database/signals.db` |
| `SYSTEM_VERSION` | Version shown in status/audit metadata | `2.0.0` |

## Authentication and account security

| Variable | Purpose | Guidance |
| --- | --- | --- |
| `JWT_SECRET`, `OAUTH_JWT_SECRET` | Signing keys | Generate unique high-entropy values per environment |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google Sign-In | Configure only with the exact staging/production callback |
| `DASHBOARD_USERNAME`, `DASHBOARD_PASSWORD_HASH`, `TOTP_SECRET` | Existing administrator authentication | Keep unique and restricted; do not reuse account passwords |
| `ADMIN_EMAILS` | Administrator email allowlist | Use verified addresses only; blank means no list entries |
| `OAUTH_JWT_EXPIRY_HOURS` | Session token lifetime | Default `168` hours |
| `SIGNAL_ENGINE_SETUP_TOKEN` | First-run setup protection | Generate a separate random value |
| `WEBHOOK_SECRET` | Telegram webhook authentication | Generate a separate random value |
| `SECURITY_EMAIL_ENABLED` | Resend account/security mail adapter | `false` until sender, browser and delivery gates pass |
| `EMAIL_ACCOUNTS_ENABLED` | Email/password account routes | `false` until staging security gates pass |
| `RESEND_API_KEY`, `SECURITY_EMAIL_FROM` | Resend account/security delivery | Server-side only; never use for trading, performance, alerts or marketing mail |
| `STRICT_SESSION_ORIGIN_CHECK` | Enforce Origin validation on unsafe browser requests | Keep `false` until custom-domain browser checks pass |

## Market and optional integrations

| Variable | Purpose | Guidance |
| --- | --- | --- |
| `TRADING_MODE` | Exchange execution mode | Keep `paper`; this source candidate is not live-certified |
| `BINANCE_DEMO_API_KEY`, `BINANCE_DEMO_SECRET` | Binance demo/test credentials | Optional; use only an authorized demo account |
| `BINANCE_DEMO_BASE_URL` | Binance demo endpoint | Defaults to the URL in `.env.example` |
| `ANGELONE_API_KEY`, `ANGELONE_CLIENT_ID`, `ANGELONE_PASSWORD`, `ANGELONE_TOTP_SECRET` | Angel One data integration credentials | Keep unset unless authorized broker configuration and network policy are verified |
| `CAPITAL` | Sizing context used by local/paper logic | `1000` in the example; not an exchange balance or performance claim |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ADMIN_USER_IDS` | Telegram alerts and restricted bot controls | Keep trading notifications on Telegram; restrict mutating commands to approved user IDs |
| `FINNHUB_KEY`, `GROQ_API_KEY` | Optional data/assistant integrations | Leave unset when unused |
| `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`, `LANGCHAIN_TRACING_V2` | Optional LangSmith tracing | Tracing is off by default; review data handling before enabling |
| `CONTENT_ENABLED`, `CONTENT_AUTO_APPROVE`, `TWITTER_*` | Optional content publishing | Keep both feature flags false; never enable automatic posting without a separate review |
| `ADAPTATION_FROZEN` | Freeze adaptive behavior | Use only under the reviewed operating procedure |

## Variables intentionally absent from `.env.example`

- `SIGNAL_ENGINE_ALLOW_LIVE_TRADING` is a separate real-order opt-in. Do not set it for this candidate; live trading has no approval here.
- `SIGNAL_ENGINE_DB_PATH` is restricted to test overrides. Production/local application storage uses `SIGNAL_ENGINE_DATABASE_PATH`.
- `DASHBOARD_API_KEY` and `RECOVERY_CODES` are generated and managed by the application; do not copy example values into a deployment.
- `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` are present in legacy configuration but are not an advertised or verified sign-in path.

The root `.env.example` is the variable-name inventory. This guide describes supported use and safety boundaries; test the actual service behavior in an isolated environment before staging.
