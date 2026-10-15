# Signal Engine V5

A Python-based market-analysis and automated trading research platform with crypto futures, Indian-market signals, risk controls, and a React dashboard.

**Status: engineering research / not approved for real-money deployment.** Profitability, exchange reconciliation and production operations have not been independently validated. Trading can lose money. See [verification status](docs/STATUS.md) before using any execution code.

## What it does

- Analyze Binance USDⓈ-M futures candles across 1h/4h timeframes with trend, momentum, volatility, and volume scoring.
- Apply individual research parameters for 18 configured coins, protective risk budgets, execution constraints and order-state journaling.
- Ingest Angel One SmartAPI Indian-market data with Redis-coordinated quotas and an opening-range signal pipeline.
- Serve APIs, notifications, research utilities, and a separate React/Vite trading dashboard.

The focus of this repository is **correctness, explainability, failure handling and reproducibility**—not a claimed trading edge. Real capital must remain disabled until the requirements in [Status](docs/STATUS.md) are met.

## Repository map

| Location | Responsibility |
| --- | --- |
| `agents/`, `engines/` | Primary signal pipeline, indicator analysis, regimes, risk and sizing |
| `trade/` | Exchange adapters, entry checks, durable order intents and reconciliation |
| `engines/indian/` | Angel One integration and Indian-market scanning |
| `backtest/` | Research data acquisition, simulation, per-coin ablation, walk-forward experiments |
| `data/`, `database.py` | Candle storage, caching and persistence |
| `api/`, `main.py` | API and service entrypoints |
| `tests/` | Isolated regression and safety tests |
| `docs/` | Architecture, research methodology, operations and verification ledger |

The separately distributed `crypto-engine-frontend-main/` repository holds the editable React/Vite dashboard source. Backend `frontend/` contains static served assets; those files are not a substitute for the React source.

## Quick verification (Python 3.11)

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests
python -m compileall -q -x 'frontend/' .
```

For an isolated subset without the full runtime stack, see the CI job in `.github/workflows/`. **Passing unit tests does not authorize live orders.** Default mode should remain paper/demo with `SIGNAL_ENGINE_ALLOW_LIVE_TRADING` unset.

### Research (no exchange keys needed)

```bash
python -m backtest.research download --coins ETH,SOL \
  --start 2024-01-01 --end 2026-10-01 --data-dir research_data
python -m backtest.per_coin_audit --data-dir research_data --coins ETH,SOL
```

Research requires intact, contiguous 1h/4h candles and real funding settlements. See [Research](docs/RESEARCH.md) for constraints and full 18-coin commands. Do not interpret illustrative samples or mocked tests as a profitable strategy.

## Technical documentation

- [Architecture and active paths](docs/ARCHITECTURE.md)
- [Research, per-coin tuning and acceptance tests](docs/RESEARCH.md)
- [Operations, backup and order recovery](docs/OPERATIONS.md)
- [Exchange/API integration and rate-limit policy](docs/INTEGRATIONS.md)
- [Engineering status and blockers](docs/STATUS.md)
- [Engineering decisions](docs/DECISIONS.md)

## Safety, licensing and provenance

Never commit broker tokens or TOTP secrets. Preserve the existing SQLite data volume and order journal on upgrades; do not replace it with an example database. Full disaster-recovery tests remain pending.

Development has involved AI-assisted implementation and review. The repository documents the actual test coverage and remaining limitations rather than implying independent certification. No root `LICENSE` is supplied; use is governed by applicable copyright law until a license is explicitly selected.

**Reproducible evidence gate:** After downloading all data and running `backtest.walkforward`, use `python -m backtest.evidence --input research_data/walkforward_results.json`. It refuses to label an incomplete 18-coin study as finished and never enables live execution.
