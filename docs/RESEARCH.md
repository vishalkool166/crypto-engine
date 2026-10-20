# Quantitative research and acceptance methodology

## Current evidence

**No configuration is certified profitable. No 50–60% winning-trade rate is demonstrated.** Exchange metadata and limited candle samples were retrieved through read-only Binance APIs, but the complete 18-coin, 1h/4h/funding archives were not materialized in this runtime. The runtime dependencies now include `ta`; the full historical experiment has not been rerun in this rebuild. Offline code tests do not measure trading edge.

## Strategy under examination

The engine follows trends using higher-timeframe EMA and ADX, lower-timeframe momentum, volume confirmation, regime checks, and coin-specific targets. The current `COIN_CONFIG` contains 18 symbols with ADX, TP, session, `skip_after_loss`, `sl`, and `tier` values. `sl` is **not** consumed by live risk calculation; numeric `tier` has no identified trading effect. Do not silently repurpose these legacy parameters or claim they were validated.

`engines/crypto/strategy.py` contains alternative, apparently unused rules; only the actual production entrypoint may define the benchmark. Preserve the exact original per-coin dictionary as a frozen reference.

## Reproducible experiment

1. Fetch **contiguous**, closed 1h and 4h USDⓈ-M perpetual candles and actual funding settlements for every configured coin. Use a common start on or after the latest contract listing (or report symbol-specific window differences). Archive the provider response, dates, hashes and metadata locally; do not fabricate missing data.
2. Run `python -m backtest.per_coin_audit` to compare the untouched live configuration, a shared reference, and *one-knob* ablations. Compare opportunity rates and rejected signals as well as P&L.
3. Run `python -m backtest.walkforward --rolling` with predeclared training/test boundaries. Parameters are picked using training data **only**. Do not repeatedly tune against the same final holdout.
4. Report OOS net expectancy, win rate, profit factor, max drawdown, fill and signal frequencies, sample counts, cost assumptions and the range of results across folds. Include error bars and account for correlated assets and multiple comparisons.
5. Run robustness sensitivity (fees, slippage, funding, intra-bar fill order, missing bars, latency, parameter perturbations). Compare price-regime cohorts and check that performance does not depend on a few outlier trades.
6. Keep any range/mean-reversion candidate **research-only** until it independently improves OOS net expectancy and drawdown and does not introduce unsafe churn. `no_trade` is a legitimate decision.
7. Paper-forward test strategy/execution agreement with an authorized account before any live proposal.

## Data commands (machine with Binance connectivity)

```bash
python -m pip install -r requirements.txt
python -m backtest.research download \
  --coins ETH,SOL,BNB,DOGE,AVAX,LINK,UNI,XRP,XLM,LTC,INJ,DOT,OP,ARB,VET,ETC,SEI,SUI \
  --start 2024-01-01 --end 2026-10-01 --data-dir research_data
python -m backtest.per_coin_audit --data-dir research_data
python -m backtest.walkforward --rolling \
  --train-start 2024-01-01 --end 2026-10-01 \
  --train-months 12 --test-months 3 --data-dir research_data \
  --output research_data/walkforward_results.json
python -m backtest.evidence --input research_data/walkforward_results.json \
  --output research_data/evidence_assessment.json
```

**Caution:** the start date must be after *every* contract's listing, and sufficient future holding-period candles must exist inside each test fold. Download rejects missing observations. The replay now embargos the final horizon both at fold boundaries **and dataset end**. Frequency is measured over the eligible calendar window, not the entire downloaded dataset.

The evidence gate is a **completeness filter**, not a statistical hypothesis test or broker certification. Even all-positive holdouts remain research-only.

## Research limitations

- Current replay uses 4h OHLC entry/exit and conservative same-candle stop priority; it does not know tick sequence or actual resting-limit fill probability.
- Funding uses available settlement timestamps but cannot reconstruct exact intra-candle fill time; record this assumption in any performance report.
- Live adaptive sizing includes portfolio state and liquidity; the research sizing is simplified. Operational parity is not yet proven.
- Closed bars, timezone-aware timestamps, full lookback, unmodified holdouts, and independent paper trading are required for credible claims.
- Win rate alone is insufficient: a 60% win rate can still lose money when average losses exceed average wins after costs.

## Acceptance gate

No automatic parameter promotion. A changed config needs positive **net** out-of-sample expectancy across multiple folds and market regimes, acceptable drawdown, robust signal frequency, statistical uncertainty, signed-off execution constraints, and a frozen holdout report. If evidence is inadequate, retain the original settings or disable the coin.
