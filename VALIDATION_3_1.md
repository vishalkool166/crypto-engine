# Signal Engine 3.1 — Validation report

## Verified in the packaging workspace

- `python -m compileall`: core Python additions, database migration code, scanner, executor and private strategy API parse successfully.
- New unified-strategy tests: **10 passed** (candidate arbitration, contradictory directions, disabled permissions, eligibility grade, sizing adapter, existing order-routing guard, config-free permission layer).
- Focused strategy, replay, trading safety, and unified pipeline suites: **71 passed** in one combined run. Broader run (excluding two modules that fail at import due to missing `slowapi`): **165 passed, 3 failed, 2 errored**. The failures/errors occurred in tests needing absent/incomplete dependencies (`slowapi`, `redis`, and `pyotp`), not in the new unified-strategy tests.
- New and modified `.tsx` files: TypeScript syntax parsed successfully using the installed global TypeScript transpiler.
- A fresh SQLite installation was successfully initialized twice; strategy permissions persisted through the second migration and the `strategy_id` columns were verified.
- No new required environment variables or third-party trading providers.

## Not verified in this workspace

- Full Python test suite: collection/tests importing `api/routes.py` require `slowapi` (already declared in `requirements.txt` but unavailable here); some expanded tests also require functional `redis` and `pyotp` installations.
- Full React/Vite build and typecheck: npm dependencies were unavailable in the offline package cache; `npm ci --offline` failed on a missing cached dependency. TypeScript syntax parsing is not a substitute for a full build/typecheck.
- Binance account access, demo fills, protective orders, Groq authentication, Docker deployment, and actual financial outcomes: credentials/runtime unavailable in the source archive.
- Real visual browser QA, accessibility audit across devices, and quantitative strategy edge are **not** claimed.

## Safety and compatibility

- Original Binance keys/env names, order journal, account switch, TOTP/live opt-in and schema are preserved.
- Initial strategy flags permit the main scanner to route orders on **the currently selected account mode**; a previously live installation must be returned to paper before deploying if paper-only behavior is desired.
- New strategy results are research candidates until they pass the normal risk/sizing/execution checks. Backtesting alone never places orders.
- Four-strategy comparison is separate per-strategy replay, not a combined portfolio backtest.
