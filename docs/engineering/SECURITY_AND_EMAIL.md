# Security specification and Resend scope lock

## Absolute Resend restriction

**Allowed email categories**: (1) verify ownership of account email and activate account; (2) password reset/recovery; (3) verify change of account email; (4) notify of security-sensitive account/password/MFA changes; (5) relevant suspicious access/security events. These are transactional security/account events only.

**Forbidden email categories**: crypto/Indian signals, position opened/closed, stop-loss/TP, performance/digests, engine uptime/incidents, general product notifications, subscription marketing, campaigns and promotional mail. Preserve Telegram or in-app channels for trading notifications. Do not build user-controlled trading email preferences. A code-level policy/enumeration test should reject any unsupported category or event mapping.

## Current source status (2026-10-19)

The candidate contains feature-gated email/password registration, verification, login and password-reset routes, plus a Resend adapter restricted to the account/security event enum. `EMAIL_ACCOUNTS_ENABLED` and `SECURITY_EMAIL_ENABLED` default to false. This is source-level implementation only: browser end-to-end behavior, delivery to a verified sender, rate limiting behind the deployed proxy, concurrent token claims, and operational recovery have not been verified. Keep both flags disabled until those gates are recorded as passed. See `RELEASE_EVIDENCE.md` for the current audit evidence.

## Identity / authentication

Source contains dashboard username/password + TOTP endpoints, Google OAuth, SaaS user sessions and API keys, as well as a separate feature-gated email/password identity path. Email identities are not silently linked to Google identities. The historical `/auth/request-totp` Telegram delivery path deserves a threat review but must not be silently removed without a compatibility decision.

### Security flow: new account / verification

- Server creates a pending-verification event after authenticated setup/registration or authorized linking. Use normalized email, expiration and idempotency policy.
- Generate a random one-time cryptographically secure token; store a keyed hash or suitably hashed token with purpose/account ID, expiry and consumed timestamp; never log the token.
- Send a link pointing to exact allowlisted app origin; validate token/purpose/expiry/account association; mark verified transactionally. Expired/replayed/wrong-user tokens fail.
- Resend sender domain must be verified; SPF/DKIM/DMARC checked operationally; API key server-only.

### Password reset / email change

- Generic acknowledgment independent of account existence, rate limits by IP/account/email, one-use time-bound proof, and password/session revocation strategy.
- Reset token only applies to eligible password-auth identity; Google-only users follow provider-specific account recovery or explicit account-link workflow.
- Email-change: prove control of new email and current session/second factor; prior email may receive security notice; audit before/after **without** recording secrets.
- MFA/TOTP reset, recovery-code regeneration and session revocation require step-up verification and explicit policy.

### Provider failure and delivery

- Use a dedicated **server-side** Resend adapter with key in secret store, network timeout, retry/backoff for safe retryable states, message correlation and provider webhook signature validation if webhooks used.
- Deduplicate event dispatch; never send reset/token raw values to logs, frontend source, dashboard WebSockets or telemetry.
- Delivery API acceptance is not proof of inbox delivery; distinguish queued/accepted/delivered/bounced where provider reports it.
- Account security may queue email; **broker order execution and safety monitoring cannot depend on Resend availability**.
- No bulk send tool, marketing lists, digest scheduler or trading alert email adapter.

## Security audit inventory

| Attack / failure | Required mitigation and test |
|---|---|
| Broken object-level auth | Role/user scoped queries; test two different non-admin accounts and admin boundaries |
| Cookie/session theft | HttpOnly/Secure/SameSite policy, appropriate expiry, server-side revocation; CSRF and Origin/proxy tests |
| OAuth redirect/CSRF/linking | State and nonce/PKCE as appropriate, redirect allowlist, email_verified claim handling, link conflicts |
| Login brute force | Persistent distributed rate limiting, safe Redis outage path, generic responses, password policy |
| Reset replay/enumeration | One-time bound token, expiry, constant public response, throttle, session revocation |
| WebSocket data leak | Per-session authentication, origin check, tier and owner filtering, re-auth/revoke on reconnect |
| API key exposure | Never return existing raw keys, store hash/scope when feasible, rotate and revoke, redact logs |
| Secrets in Git/build | Precommit/CI scans, `.env.example` placeholders, isolated deploy secrets and rotation drill |
| Unauthorized trader action | Server-side role + step-up auth, CSRF defense, audit, no auto-execution by demo routes |
| Unsafe TOTP/2FA recovery | Rate limits and mandatory proof; avoid logging QR provisioning secrets |
| Unsafe file/static route | Path traversal and secret download negatives for SPA fallback, private files excluded |
| Unbounded compute or provider abuse | Request size/time limits, quotas, safe error messages, Redis/Angel One fail-closed behavior |
| Supply-chain compromise | Dependencies and CI pinning, SBOM, action permissions, no private registry assumptions |
| Data privacy | Least PII retention, redaction, rights/retention policy and audit controls |

## Design constraints for admin controls

Destructive or risk-increasing actions require confirmation, a visible precise target, server-side permission check, audit entry and possibly TOTP re-verification. Frontend hiding does not substitute for API restriction. Auth-related state belongs in **Settings → Account & Security**, not trade notification settings.

## Credential handling for this project

Do not share AWS keys, Binance/Angel One keys, Google client secrets, Resend API key, TOTP codes or live database in chat or Git. Use redacted config names, staging test accounts and provider dashboards for credential creation. Token rotation on any suspected exposure is an operational task.
