# Security boundary

## Credentials

Exchange keys, Google client secret, Telegram token, Tunnel token, session secret, and origin proxy secret are backend/provider configuration. None is a VITE variable or browser build value.

scripts/setup_env.py creates random application secrets in a private .env without printing them. It leaves provider credentials empty; it does not simulate provider connectivity. Production startup rejects missing Google credentials or weak application secrets. Existing .env files are never overwritten by that script.

Default to Binance demo credentials. Optional live credentials require the explicit opt-in and transition controls in [EXECUTION_MODES.md](EXECUTION_MODES.md). Do not configure withdrawal permission. Restrict keys by IP where the exchange supports it. Rotate any key that was committed to a repository, log, or released archive. Git history is not present in the supplied ZIP and must be reviewed in the actual GitHub clone.

## Operator sign-in

Google is the only web login. A verified email must exactly match ADMIN_EMAILS; its Google subject is pinned on first valid login. Sessions are random opaque tokens stored only as SHA-256 hashes in SQLite. Cookies are host-only, Secure and HttpOnly in production, with SameSite=Lax. Logout revokes the database session. Session expiry and email-allowlist changes are checked for every admin request and periodically on private streams.

There are no master API-key, password-reset, bootstrap, customer signup, tier editor, or subscription endpoints.

Google account recovery is the operator’s primary recovery mechanism. If Google subject binding must be changed, perform an audited offline database operation after identity verification and revoke sessions. No unauthenticated recovery URL exists.

## Step-up verification

Position closes and both execution-mode switch directions require TOTP. Set TOTP_SECRET privately on AWS and enroll it in your authenticator locally; do not place its QR code in the public app. Verification uses Redis to reject reuse for 90 seconds and fails closed if Redis is unavailable. Never print this secret in logs.

## Network and abuse controls

Docker publishes neither Redis nor API ports. Cloudflare Tunnel is the only application ingress. The scoped Pages Functions inject a separate origin-verification secret, so direct requests to the backend cannot use the APIs. Uvicorn does not trust arbitrary forwarded headers.

Backend request budgets, payload limits, WebSocket connection caps, exact-origin checks, and per-session CSRF tokens add application controls. Configure Cloudflare WAF/rate-limiting rules for the public API, admin authentication, and expensive operations. Do not apply interactive challenges to the Telegram webhook or OAuth callback. Webhook secret validation and administrator chat/user allowlists remain mandatory.

A private Telegram chat defaults to its own sender ID. Group chats require TELEGRAM_ALLOWED_USER_IDS. Commands require Redis-backed deduplication and budgets. Free-text model access is disabled unless ENABLE_TELEGRAM_ASSISTANT=true.

## Deployment controls

Secure .env and database backups. On AWS, restrict SSH to operator addresses. Run one engine instance. Do not mount the Docker socket or grant the application Docker-administration privileges.

Static Pages assets emit CSP, frame denial, MIME sniff prevention, referrer policy, and permissions policy. API responses are marked no-store and receive MIME-sniff and referrer protections. API/auth responses are not cached. Public data remains publicly copyable; the application does not promise scrape-proof content or immunity from attacks.

## Reporting a problem

Do not publish credentials or account data in GitHub issues. Privately contact the repository owner with affected endpoint, timestamp, reproducible steps, and redacted evidence.
