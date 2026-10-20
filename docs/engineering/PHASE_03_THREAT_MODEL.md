# Phase 03 authentication and session threat model

**Scope:** source candidate review for the Signal Engine API, dashboard and optional SaaS account flows. This is a local engineering artifact dated 2026-10-20. It does not certify the deployed AWS service.

## Assets and trust boundaries

| Asset | Boundary / principal | Security expectation |
|---|---|---|
| Exchange credentials, orders and shared account state | Operator/admin APIs and engine runtime | Only trusted administrators can invoke trading controls; ordinary API credentials cannot inherit operator privileges. |
| User identity, sessions and subscription tier | Google OAuth, optional email account, browser cookie, API key | Identity is bound to a provider subject; disabled users and revoked sessions fail closed; tier is enforced by the backend. |
| Dashboard and WebSocket data | Browser origin to API/WebSocket | Authenticate the session, restrict admin diagnostics, and reject untrusted cookie-backed mutations when the origin guard is enabled. |
| Password reset and verification challenges | Public email endpoints and configured delivery provider | Feature flags, one-use time-bounded challenge, throttling and generic recovery responses limit abuse and account discovery. |
| Deployment configuration and secrets | Operator environment / AWS runtime | Secrets stay server-side; source checks do not reveal live environment values or prove deployment configuration. |

## Threats, controls, and remaining evidence

| Threat | Current source control and local evidence | Open verification / residual risk |
|---|---|---|
| Anonymous or lower-tier caller reaches admin/trading data | Endpoint authorization inventory covers 129 route operations; static matrix checks router helper semantics and admin grouping. Trading and engine-health router helpers require admin; ordinary API routes require authentication. | No live HTTP/WS negative-role matrix or tenant-isolation run. Static route inspection cannot prove every runtime dependency or response payload. |
| CSRF through a browser session cookie | Optional `STRICT_SESSION_ORIGIN_CHECK` middleware rejects unsafe cookie-backed requests with a missing or untrusted Origin. Unit checks cover blocked origin, accepted origin, safe GET and token-only caller. | The switch defaults off to preserve existing AWS behavior. Enable only after staging browser, custom-domain cookie, automation-client and proxy checks. CSRF protection is not yet certified for production. |
| Forged or misbound Google identity | OAuth callback requires a verified email and nonempty provider subject; user provisioning checks provider identity and does not silently link another provider. Source inventory checks OAuth authorization flow and claim validation. | Full Authlib state/nonce/callback adversarial tests and browser sign-in against Google remain open. |
| Stolen personal API key gains administrator power or persists indefinitely | Personal keys are hashed at rest, expire 90 days after creation, are limited to GET/HEAD/OPTIONS, and are forced to non-admin identity. Tests cover expiry, revocation, role downgrade and method restrictions. | Existing keys created before expiry enforcement may have no expiry; rotate those keys. The separately configured global dashboard master key remains privileged and requires operator secret-management controls. |
| Brute force or recovery-token abuse | Login/reset paths use persisted throttles and one-use challenge checks; API-key creation validates its name and is rate-limited. Email account functionality requires both security email and account flags. | Provider delivery, concurrency/failure handling and user-enumeration behavior need staging verification; email accounts remain disabled by default. |
| Cross-tier WebSocket data disclosure | Dashboard WebSocket uses session middleware and an origin check when an Origin is supplied; admin diagnostics are constructed only for admins. Route inventory protects the WebSocket path. | Cross-tier browser/WebSocket tests, origin-omission policy and reconnect behavior remain open. |
| Internal exception or secret leakage | API inventory and existing error handling checks are local source evidence; credentials are not part of this artifact. | Run deployment-level log and response review with sanitized staging data. |

## Verification boundary

Local checks can validate source structure and isolated helper behavior. They cannot establish the live route table, reverse-proxy headers, cookie attributes after deployment, provider callbacks, shared Redis/session state, rate-limit behavior across workers, or actual user/tenant data isolation. Keep the authentication and release tasks in `MASTER_TASK_LEDGER.csv` as `IMPLEMENTED_UNVERIFIED` or `PLANNED` until those gates are exercised.
