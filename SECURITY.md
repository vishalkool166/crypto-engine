# Security policy

Signal Engine handles exchange credentials, account state and an administrator session. Treat vulnerabilities affecting trading, authentication, request boundaries and stored secrets as sensitive.

## Reporting a vulnerability

**Do not disclose an exploitable finding or credentials in a public GitHub issue.** If GitHub private vulnerability reporting is enabled for this repository, use **Security → Report a vulnerability** to send the finding to the repository maintainers. If that option is not enabled, request a private reporting channel from the repository owner without including exploit details in the public request. No monitored security email or response-time commitment is asserted by this source distribution.

Include affected version/commit, conditions needed to reproduce, observed impact and minimally sufficient reproduction steps without real account secrets. Avoid submitting real orders or affecting third-party systems during verification.

## Supported versions

Security fixes target the current maintained source release. At publication this is **3.4**; older ZIP releases and detached forks are not represented as supported. Users operating forks or older snapshots should compare them with the latest published source and update cautiously after taking backups.

## Safe deployment baseline

- Keep `.env` outside version control and restrict file/volume permissions. Rotate credentials if exposed.
- Use dedicated, least-privilege Binance API keys with withdrawal permission **disabled** and IP restrictions when supported.
- Keep Redis, FastAPI and Docker socket off the public Internet. Proxy only the routes needed by enabled interfaces; never expose `ORIGIN_PROXY_SECRET` to browser code.
- Require Google allowlist and HTTPS for the private console, use TOTP for account-mode switches, and review the operator audit history.
- Back up application data before upgrading. Reconcile positions and unresolved order intents before trading after an outage or restore.
- Do not enable live mode merely because the repository builds or tests pass; verify the account, protective orders and exchange behavior in demo first.

See [Operations](docs/OPERATIONS.md) and [Deployment](docs/SELF_HOSTING.md) for controls and recovery procedures.
