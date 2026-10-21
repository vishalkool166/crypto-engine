# Design decisions

- Keep `dashboard/` as the only frontend source. Build it in public and admin modes for two Cloudflare Pages projects.
- Keep FastAPI, SQLite history, Redis, and cloudflared on the existing AWS deployment.
- Use Pages Functions scoped to API, auth, WebSocket, and webhook paths; static assets and SPA routes remain Pages assets.
- Keep browser requests same-origin so admin cookies and CSRF checks remain effective.
- Keep Google sign-in limited to `ADMIN_EMAILS`; do not add customer accounts, billing, or public login.
- Default to paper; require explicit server opt-in, TOTP, flat-account checks and a process restart for live activation. Require selected-account credentials and reconciliation before scheduled operation.
- Keep public API response fields explicitly allowlisted.
- Do not include secrets, database data, dependencies, built assets, or Git history in release archives.
