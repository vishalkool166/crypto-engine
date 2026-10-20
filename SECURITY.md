# Security policy

This repository includes authentication, broker integrations and code capable of placing real orders. Treat vulnerability reports as sensitive. Do not publish exploit details, API keys, account identifiers or real order data in public issues, screenshots or logs.

## Operational rules

- Keep this repository private until the maintainer completes a history-wide credential scan and confirms no credentials were previously committed. Current-tree scans do not inspect historical commits.
- Never commit `.env`, account tokens, Google OAuth secrets, TOTP seeds, broker keys, SQLite databases, Redis dumps, recovery codes or vector stores.
- Keep `TRADING_MODE=paper` and production change permissions restricted until independent exchange/broker safety verification is complete.
- Resend is approved for **account setup and security** emails only, never signals, trading, engine alerts, performance, marketing or digests.
- `SECURITY_EMAIL_ENABLED=false` stays in effect until issuance/consumption, expiry, rate limits and session invalidation flows pass their acceptance tests.
- `STRICT_SESSION_ORIGIN_CHECK=false` is a migration-safe starting value. Before enabling, test same-site custom-domain cookies, CORS preflights and all authenticated mutation clients against a staging backend. Once enabled, unsafe browser requests must supply an approved `Origin`.
- Do not print secrets while collecting support information. Sanitized error type, request ID and approximate time are sufficient for initial investigation.

## Report a vulnerability

Contact the repository owner privately through the GitHub repository's existing authorized channel. Avoid testing against real funds or customer accounts. Create a reproducible isolated proof of concept with synthetic records and a proposed severity assessment.

## Unsupported assumptions

A passing unit test suite, Cloudflare deployment success, or GitHub's security indicators cannot certify broker safety or a vulnerability-free application. Additional paper-mode and independent production-change reviews are mandatory.

## Email account feature gate

Email/password accounts are implemented for future activation and **disabled by default**. Both `EMAIL_ACCOUNTS_ENABLED` and `SECURITY_EMAIL_ENABLED` must be enabled after a verified provider domain, browser/OAuth coexistence, account linking policy, secure cookies, session revocation, and abuse testing. Email delivery is exclusively for account setup and security; no market, system, performance or marketing email is permitted. Never send a user a raw verification token outside the authorized inbox flow. See `docs/engineering/RELEASE_EVIDENCE.md`.
