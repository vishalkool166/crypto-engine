# Controlled deployment: one GitHub monorepo, AWS engine, Cloudflare dashboard

**Status: implementation guide, not proof of a successful production cutover.** No production credentials or production git branch have been accessed in this release.

## Invariants

- The original backend files `main.py`, `Dockerfile`, `docker-compose.yml`, `scheduler.py`, `config.py` and the Python import root stay in the same locations. Do not rename services, database mounts, or start a second scheduler.
- Preserve `./database` and the Redis named volume on EC2; **never** replace them with empty source or example state. Back up SQLite with its online backup API while the engine is operating; preserve WAL integrity.
- Build Cloudflare Pages only from `dashboard/` (`npm run build` -> `dist`). In the Phase 01–02 **candidate**, old `frontend/` is removed and AWS HTML routes redirect to Cloudflare. The currently running AWS version may still serve those files; only cut over after staged build and rollback checks.
- Resend is disabled until full account lifecycle security is implemented and verified. No trading emails.

## Safely apply the downloadable ZIP to your existing Git repository

1. From your normal developer machine, `git clone` the existing **`vishalkool166/crypto-engine`** if necessary (or use your existing checkout). Verify `git remote -v`, your production branch and `git status`. **Do not delete the `.git` directory.**
2. Record the deployed AWS commit, Docker/Compose update method, environment variables **by name only**, database backup location, and rollback procedure. If AWS automatically updates from every push to `main`, protect that branch and do not push these changes there yet.
3. Create an isolated branch: `git switch -c engineering/aws-pages-monorepo`. Download/extract the new source ZIP into a separate temporary directory. Copy its **file contents** into the existing checkout while preserving `.git`, `.env`, `database/`, Redis data and other runtime volumes. Example using `rsync` from the extracted archive's root:

   ```bash
   rsync -av --exclude='.git' --exclude='.env' --exclude='database/' --exclude='redis_data/' --exclude='*.db' --exclude='*.sqlite*' EXTRACTED_ROOT/ EXISTING_CHECKOUT/
   ```

   This command **does not delete stale files** by itself. Explicitly remove `.github/workflows/` from the checkout (the user chose no Actions), then verify changes with `git status` and `git diff --check`. Never blindly use `rsync --delete` against a checkout with live data.
4. Check the protected runtime files in `docs/engineering/UPSTREAM_RUNTIME_SHA256.json`: they should be unchanged. In Phase 01–02, `main.py` also removes legacy static/template serving and redirects known browser entrypoints to Cloudflare. Review this change in staging before production. Review additions to `api/`, `trade/`, `saas/` independently.
5. Run `bash scripts/verify_local.sh`. With npm access, run `CHECK_FRONTEND=1 bash scripts/verify_local.sh`. A local pass does not prove AWS compatibility; stage the backend separately in **paper/demo** mode and verify auth, CORS, WebSockets and DB backups before production.
6. Commit this branch; push it for review. Only merge to your AWS auto-deploy branch after a verified backup/rollback rehearsal. Keep the old SHA available for `git revert`/rollback.

## Cloudflare Pages configuration

| Option | Setting |
| --- | --- |
| Git repository | `vishalkool166/crypto-engine` |
| Project type | Pages (Git-connected) |
| Production branch | Existing, verified application release branch (usually `main`) |
| Root directory | `dashboard` |
| Build command | `npm run build` |
| Build output | `dist` |
| Node version | 22 |
| Build watch include paths | `dashboard/*` (avoid rebuilds on Python-only changes) |
| `VITE_API_URL` | `https://signal-engine-v5.vishalkool.top` (verify actual production origin first) |
| `VITE_WS_URL` | `wss://signal-engine-v5.vishalkool.top` (verify actual WebSocket endpoint first) |

DNS: use a dashboard subdomain such as `app.vishalkool.top` if owned/configured. On the AWS server explicitly set `FRONTEND_URL=https://app.vishalkool.top` to match the real Pages domain. Existing CORS middleware allows configured `FRONTEND_URL`; OAuth's callback remains on the AWS domain but returns to that configured frontend origin after login. Do not share credentials or JWT secrets with Pages. The browser must send session cookies over HTTPS and, when using same-site subdomains, verify browser SameSite/Secure behavior in real Chrome/Safari/Firefox.

**Warning:** `*.pages.dev` preview URLs are cross-site from `vishalkool.top`. Browser cookie rules may reject authenticated sessions on previews; verify on a controlled custom domain rather than bypassing cookie security.

## Acceptance test before cutover

- Verified frontend `npm ci`, lint, TS check, Vite production build, and deep-link reload on Cloudflare.
- User and admin login, Google OAuth callback, logout, session expiry, CORS preflight and cookie attributes.
- Authenticated API requests and dashboard WebSocket must hit **AWS**, not Cloudflare Pages static `index.html`.
- Signals and trades pagination must show consistent counts/sorting across page boundaries; user/admin roles enforced by backend.
- Verify admin, audit and account actions, loading/empty/error states on mobile and desktop; no demo data misrepresented as live data.
- Verify one and only one backend scheduler, no order duplication, stable Redis connections, actual journal and database state; keep live trading disabled in staging.
- Verify new backend container startup with the old `frontend/` removed; check `/`, `/login`, `/auth/google`, `/auth/callback/google`, `/api/health`, `/ws/dashboard` and unknown routes.
- Exercise a rollback to last known working AWS commit and Cloudflare deployment; check that sessions and records remain intact.

## AWS auto-update unknown

The original uploaded archive does not show how your running EC2 instance auto-updates from GitHub. It may use a cron pull, webhook, service, deployment agent, or manual script. **Never assume that Pages Git builds replace the existing AWS deployment mechanism.** Verify it before pushing to the production branch.

## Explicit release blockers

Provider login tests, full Resend token lifecycle, real Redis Lua tests, exchange demo/testnet error-path drills, Python 3.11 Docker build and end-to-end browser tests are not certified by this local package. Production/live-capital approval requires independent review.
