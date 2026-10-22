# Signal Engine 3.1 — Unified Strategy & Interface Upgrade

## Scope

This release extends the existing FastAPI + SQLite + Redis + Binance + Groq service. It is **an in-place source update**, not a new project. It adds **zero required environment variables, zero new APIs, and no Hyperliquid dependency**. Keep the existing `.env`, administrator accounts, Google OAuth config, Binance demo/live credentials and runtime state on your server. Never upload live credentials or `.env` to GitHub.

The **existing** global paper/live switch and its opt-in, TOTP, flat-account checks, restart and reconciliation stay in control of account mode. On a new installation the mode still defaults to `paper`; on an existing installation its persisted mode is preserved by design. **If an existing server is already live, deploying this release can place live orders from the newly enabled strategies. Switch to paper before deploying.**

## What changed

```text
Binance 4H closed candles + 1H data-quality check
             |
        Shared features
             |
  +----------+----------+-----------------+-----------------+
  |          |          |                 |                 |
  S1         S2         S3                S4                 |
  Trend      Breakout   Range             Momentum           |
  continuation retest   reversion         reversal           |
  +----------+----------+-----------------+-----------------+
             |
    Persist every decision / rejection
             |
    Eligibility and conflict arbitration
        |                         |
    No trade                  One proposal per symbol
                                  |
                       Common sizing / risk governor
                                  |
                       Existing Binance order journal
                                  |
                        Existing demo / live executor
```

Each S1–S4 has independent entry and stop/target logic, one shared portfolio and one execution path. They do not require approval from each other, but **contradictory LONG/SHORT candidates are rejected rather than netted, averaged or executed twice**. If several compatible candidates exist, the stable arbiter chooses one using the explicit heuristic score and fixed tie-break. These scores are NOT predicted win probabilities.

The four strategy definitions in `strategies/registry.py` are reused by both the production scanner (`strategies/pipeline.py`) and the research replay (`research/lab.py`). The older parallel trend-only `agents/signal_agent.py` remains for legacy diagnostics but is no longer called by the crypto scanner.

### Operator controls

In the existing administrator app: **Overview** shows the real-time control board; **Strategy Laboratory** contains persistent per-strategy scanning and execution controls, the closed Binance candlestick chart with stop/entry/target annotations where decisions exist, separate replay and four-way comparison, market intelligence, recorded main-scanner decisions, separate-mode trade attribution and the existing evidence/AI assistant.

All four strategies are initially `scan_enabled=true, execution_enabled=true` **in the existing SQLite database**. This means they can route risk-approved orders on the configured account; it does **not** bypass the global mode toggle. Turning off one strategy does not stop the other three. No new `.env` switches are necessary. If the operator wants observation only, disable its Execute switch in the Strategy Laboratory.

The private app uses Google access control plus existing server-side anti-CSRF request handling. The public site does not expose private account information. The public `/status` page now reads the mode returned by the existing API, rather than hardcoding `Paper`.

### Automated schema evolution

Existing `database.init_db()` adds `signals.strategy_id` and `trades.strategy_id` when missing and creates/initializes `strategy_controls` without erasing existing rows. The existing `strategy_shadow_observations_v3` table is retained as the **main-pipeline decisions history** for backwards compatibility and is bounded as before. No manual SQL migration is required.

### Historical experiment caveat

The new `POST /api/v1/admin/strategy-lab/compare` runs four **separate** same-data historical simulations; the totals are not an executable combined portfolio backtest. Existing replay omits funding/liquidation/microstructure and does not model entire live account state. Its results are uncertified and must never be interpreted as guaranteed edge. `GET /api/v1/admin/strategy-lab/performance` reports only recorded closed trades, and keeps paper vs live mode separate.

### Sources and API endpoints

- `strategies/registry.py`: four deterministic strategy rules and feature functions.
- `strategies/pipeline.py`: arbitration + shared sizing + decision output. **No exchange calls**.
- `strategies/control.py`: per-strategy permissions persisted in SQLite.
- `alerts/scanner.py`: main scanner calls the unified pipeline and existing order executor.
- `trade/executor.py`: original order journal, stop protection, duplicate prevention, and per-strategy trade ownership.
- `api/strategy_lab.py`: authenticated strategy registry/controls/candles/performance/replay/comparison endpoints.
- `dashboard/src/components/StrategyBoard.tsx`: four-strategy operator display and switches.
- `dashboard/src/components/StrategyChart.tsx`: stored Binance candlesticks and volume, with actual decision levels where available.
- `dashboard/src/features/public.tsx`: research narrative, diagram and dynamic evidence metrics.

## Deployment (keep current setup)

1. **Confirm that the existing global mode is PAPER.** Stop the old application instance before replacing the repository so no two scanners overlap.
2. Back up `database/`, `.env`, volumes and your current deployment files (do not publish them).
3. Replace project source with this release. Preserve the existing `.env`, database volume, `runtime_state` and existing credentials. Do not copy the packaged `.env.example` over `.env`.
4. Use the *existing* deploy command. Its startup invokes `init_db()` and handles the new strategy controls and columns automatically. If deploying via Docker, rebuild the images so the new frontend is compiled.
5. In the admin app, confirm the current paper/live mode, scan status, four strategy switches, closed-candle chart, and saved decisions. Test exchange-demo order and stop behavior before considering any future live use.
6. A later live transition uses the **already-existing** operator switch, which requires the original server live credentials, TOTP and live opt-in. If those were never configured, this release does not invent or retrieve them.

## Validation and limitations

- `python -m pytest tests/test_unified_strategy_pipeline.py` tests conflict resolution, permission gates, sizing adapter, and use of the existing executor.
- `python -m pytest tests/test_strategy_lab_v3.py tests/test_strategy_replay.py tests/test_trading_safety.py tests/test_p0p1_strategy_safety.py` tests the original strategy/replay and protective rules.
- `cd dashboard && npm ci && npm run build` checks types and compiles both public and admin builds.
- Authenticated Binance/demo credentials and Groq need verification on the **deployment server**. They are not present in the uploaded source ZIP.
- **No strategy has been certified profitable**. Nothing in this release is investment advice or a promise of execution reliability.

## Known release-verification gap

In the packaging environment, the `slowapi` Python requirement and npm tarballs were unavailable for download. Therefore the complete FastAPI test suite and production React/Vite build could not be run here. The exact gaps and test totals are recorded in `VALIDATION_3_1.md`. Treat this as a **source release requiring server-build and exchange-demo acceptance checks**, not as a deployment-verified binary.
