# Signal Engine 3.3: verification notes

## Verified in this environment

- TypeScript parser completed all **28** frontend TS/TSX source files with **zero syntax errors** using TypeScript's compiler API. This is a *syntax check*, not a full typecheck or production bundle.
- Stylesheet was parsed with `tinycss2`; **zero CSS parsing errors**.
- **53 regression tests passed**, including unified strategy pipeline, strategy replay, Strategy Lab and order safety tests: `PYTHONPATH=. pytest -q tests/test_unified_strategy_pipeline.py tests/test_strategy_replay.py tests/test_strategy_lab_v3.py tests/test_p0p1_strategy_safety.py`.
- The three-bar logo's React markup and favicon/PWA SVG and regenerated PNG assets are present. The old diamond markup and S/E login glyph have been removed.
- Binance/Groq Python modules and existing configuration keys were not modified by this frontend-only release.

## Not verified here

- `npm ci --offline` failed: npm cache has no `yallist-3.1.1.tgz`; therefore `npm run build` and complete TypeScript typechecking were not run. This does not establish a frontend compilation failure or success.
- Chromium/Playwright navigation to local preview HTML was blocked by the container's administrator policy; no browser-rendered build screenshots, mobile visual QA or interactive motion QA were verified. Static layout preview HTML files generated during development are not proof of the deployed React app.
- No authenticated Binance account connection, Groq key, real exchange order or live-mode switch was exercised.
- No strategy profitability validation was performed.

## Deployment acceptance

Run `cd dashboard && npm ci && npm run build` on the deployment build machine, test both public/admin URLs, then verify all routes, browser console, navigation, four strategy controls, research comparisons, real price charts, authentication, execution-mode permission dialog, reduced-motion support, all responsive breakpoints, and cached PWA icon replacement. Preserve the existing `.env` and database. Confirm paper mode before allowing the scheduled scanner to run after updating.
