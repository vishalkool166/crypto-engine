# Signal Engine 3.2 — Atelier Design Validation

## Checks performed

- Frontend TypeScript/TSX parse: **28 files; zero syntax errors**, using global TypeScript parser.
- Selected changed TSX transpilation: **6 files; zero diagnostics**.
- PostCSS stylesheet parse: **valid**.
- Focused Python trading/replay/strategy regression: **71 passed**.
- Browser-rendered design snapshots generated at 1440px from source-derived static HTML using Chromium; these are **not the compiled React site**.
- Source structure and existing Binance/Groq/environment-variable interfaces retained from 3.1; no new setup or secrets required.

## Not verified here

- Full `npm ci` and Vite production build: dependency retrieval unavailable in this workspace. A local offline attempt failed due missing tarballs; an online attempt timed out. There is no verified compiled `dist` in this release.
- End-to-end browser QA of mounted React components, login, authenticated API data, all breakpoints and live navigation.
- Authenticated Binance/Groq connectivity, demo/live order fills and financial results.
- Awwwards award score or near-10/10 craft rating: these are aspirational design criteria, not independently verified outcomes.

## Deploy/rollback

1. Back up the current repository/database and runtime settings before updating.
2. Replace the repository source, preserving your current deployment's environment credentials and data mounts. No new `.env` fields required.
3. Run the existing dashboard deployment pipeline (`npm ci && npm run build` in `dashboard/`, or the configured Cloudflare build command). Verify both public/admin entry builds.
4. Test public `/`, `/signals`, `/performance`, `/methodology`, `/status` and private `/`, `/strategy-lab`, `/trades`, login, mode display, and scan action against the real backend. Test mobile as well.
5. Confirm existing account paper/live mode and Binance profile before enabling any order flow. UI versioning does not silently change execution permissions.
6. Revert frontend files to 3.1 if the build or visual smoke tests fail; backend/data shape is unchanged in this visual release.
