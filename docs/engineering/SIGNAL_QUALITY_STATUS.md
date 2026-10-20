# Signal quality status — not evaluated

**Current conclusion: NOT EVALUATED.** The source package contains no approved, immutable historical dataset for the required 18 symbols, no verified funding series, and no completed untouched walk-forward holdout report. No win rate, expectancy, profit factor, Sharpe ratio, drawdown, or profitability claim is reported here.

## Frozen baseline and current evidence

- The candidate's S0 strategy-file baseline is guarded by `scripts/freeze_strategy_baseline.py --check` (15 source-file hashes). This protects source inputs from silent edits; it does not show that S0 is profitable or that historical outputs are deterministic for every environment.
- Existing research tooling includes dataset manifest/checksum validation, closed-candle checks, chronological walk-forward evaluation, and an evidence gate that never approves live trading.
- The locally supplied source tree contains no research dataset files or saved walk-forward results. The research pipeline therefore cannot produce defensible numerical performance results from this package alone.
- Execution costs, realistic fills, funding, latency, correlated portfolio exposure, and forward-paper outcomes have not been validated end to end.

## Required evaluation before any signal-quality claim

1. Acquire an authorized, provenance-recorded dataset for every required symbol, including candles and funding where applicable; preserve raw files and SHA-256 manifests.
2. Validate timestamp alignment, exchange gaps, duplicate rows, timezone conventions, closed-candle use and delisted/symbol-change handling.
3. Freeze the S0 logic and parameters before evaluation. Record the exact code hash, configuration, dataset hashes and runtime versions.
4. Run chronological walk-forward/untouched holdouts with fees, slippage, funding, order latency and conservative fill assumptions. Do not tune on the holdout.
5. Report signal count/frequency, fills, net expectancy, profit factor, drawdown, tail losses, turnover, costs and uncertainty by symbol and regime. Include negative and incomplete results.
6. Compare any experimental strategy with the same protocol; do not promote it automatically. A favorable backtest is research evidence only, not live approval.
7. Continue a separately logged forward-paper period before considering a controlled testnet drill.

## Promotion decision

No candidate is promoted. No strategy parameters were changed during this work batch. The task remains open until data coverage, reproducible holdouts, execution realism and independent review are available.
