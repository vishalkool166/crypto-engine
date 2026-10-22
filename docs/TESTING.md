# Testing and release acceptance

Testing is divided into fast source checks, integration checks and deployment verification. A package can pass static checks while still failing to build or connect to an exchange.

## Reproducible commands

```bash
# Python 3.12 in a virtual environment
python -m pip install -r requirements-dev.txt
python -m compileall -q .
PYTHONPATH=. python -m pytest -q tests

# Node.js 22, in dashboard/
cd dashboard
npm ci
npm run check
npm run build
npm test
```

If Playwright browser binaries are absent: `npx playwright install --with-deps chromium`. Never label TypeScript AST parsing as a complete `npm run build`; they test different properties.

## Required coverage for changes

| Change | Minimum regression cases |
| --- | --- |
| Strategy rule | Positive candidate, rejected condition with actual/threshold evidence, invalid indicators, no lookahead, data-boundary behavior |
| Trade levels | Long/short order of stop/entry/target, insufficient available reward, stale levels, costs and risk governor compatibility |
| Execution | Mode guard, per-strategy permission, same-coin conflict, duplicate order intent, uncertain fill/reconciliation, restart state |
| Scanner | All configured symbols accounted for, partial failure, stale scan, cooldown/in-trade protection, API throttling |
| Persistent records | Fresh DB, pre-update DB copy, restarts, expiry without deletion of audit records |
| UI | Public/admin route separation, Google session, click-anywhere drawer, keyboard and focus, trade ruler in both directions, dark/light, reduced motion and mobile widths |

## Distribution integrity

On an extracted archive, `python scripts/verify_manifest.py` compares the packaged source against `SHA256SUMS`. This detects content corruption but is not a cryptographic publisher signature.

## Deployment acceptance checklist

1. Snapshot `.env`, SQLite database, runtime state and volumes; verify the saved mode is **paper**.
2. Install exact package dependencies and complete backend and frontend tests; investigate every failure.
3. Deploy both selected interface builds behind the trusted proxy; verify route fallback and correct hosts.
4. Verify Google login, session/CSRF, no unintended public/admin data crossover and appropriate HTTP errors.
5. Perform a complete Binance demo scan: all configured coins accounted for; inspect multiple strategy traces and chosen/no-entry decisions.
6. Exercise demo order creation, stop/target attachment, reconciliation after restart, data staleness and duplicate suppression. Do not test with live keys.
7. Inspect System Health values; label unavailable Docker or EC2 info as unavailable.
8. Verify the Trade Journey animation with real stored observations, both themes, mobile drawer scrolling and reduced-motion support.
9. Confirm Telegram and Groq behavior only if configured; verify alert delivery and assistant errors/fallbacks.
10. Require a separate future live-readiness review and explicit user action before live mode is ever enabled.

[Current 3.4 validation evidence](VALIDATION.md) records what has **actually** run, including incomplete tests and the unavailable production browser build.
