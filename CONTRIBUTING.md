# Contributing to Signal Engine

Thanks for improving Signal Engine. Contributions should make the system easier to understand, safer to operate, or more thoroughly verified. A new trading rule is not evidence of an edge until it is measured.

## Before opening a pull request

1. Search existing issues and pull requests for related work; open a design issue first for changes to execution safety, persistent schemas, authentication or strategy contracts.
2. Fork the repository and create a focused branch. Keep unrelated formatting and feature changes out of the same pull request.
3. Include automated tests for changed behavior. For strategy changes, include rejection cases and deterministic, closed-candle fixtures; for UI changes, address dark/light mode, keyboard access and reduced motion.
4. Do not commit `.env`, API keys, databases, user/trade exports, log files, screenshots containing account values, or credentials in fixtures. Use synthetic values.
5. Explain the operational effect and a rollback path when altering persistent storage, API contracts, execution permissions or order handling.

## Local verification

Backend (Python 3.12):

```bash
python -m pip install -r requirements-dev.txt
python -m compileall -q .
python -m pytest -q tests
```

Frontend (Node.js 22):

```bash
cd dashboard
npm ci
npm run check
npm run build
npm test
```

Playwright browser tests may need browsers installed separately: `npx playwright install --with-deps chromium`. Full external-account and production-browser checks are a separate deployment acceptance step; do not claim them completed from mocked tests.

## Pull request description

Provide a short problem statement, user-visible changes, relevant modules/records, tests executed **with results**, any tests that could not run, and an upgrade/rollback note. Attach screenshots or recordings for UI changes when possible. Label synthetic market data as synthetic. Keep source claims aligned with implemented behavior.

## Code ownership principles

- `strategies/registry.py` defines deterministic strategy evaluations used by both scanner and replay. Avoid separate research-only copies of a trading rule.
- `strategies/pipeline.py` arbitrates candidates; `alerts/scanner.py`, `trade/` and the risk checks control execution. Strategy logic must never submit orders directly.
- `database.py`, `research/ledger.py` and `runtime_state.py` own durable state. Preserve existing data and test migrations/restarts.
- `api/` owns backend HTTP contracts; `dashboard/src/` owns the interfaces. Private operator routes must retain authentication and request protections.
- `docs/` should describe current code rather than planned or speculative features.

## Review standards

Maintainers may ask for evidence or changes before merging, especially where an edit changes exposure, stop behavior or account-mode protections. Proposed strategy improvements must report costs, holdout boundaries, sample sizes and uncertainty. Do not present win rates or backtests as guaranteed future performance.

For vulnerability reports, follow [SECURITY.md](SECURITY.md) rather than filing public issues.
