# Research methodology and evidence standard

## Current status

**None of the four strategies has a certified profitable edge.** The 18-symbol rolling research gate is incomplete: [`RESEARCH_GATE.json`](RESEARCH_GATE.json) records zero of 18 symbols evaluated against the required data and evidence criteria. Passing code tests or generating simulated trades is not a profitability demonstration.

## Shared strategy rules

Four strategy evaluators are implemented in `strategies/registry.py`: trend continuation, breakout/retest, range reversion and momentum reversal. The live scanner and historical replay call the same deterministic evaluator functions, but they do **not** share all execution conditions. Exchange latency, actual fill quality, partial fills, funding, leverage, portfolio interactions and liquidation behavior require separate demo validation.

The engine proposes targets from observable closed-candle structure (or a qualifying measured breakout range) rather than automatically applying a fixed profit multiplier. This does not establish a target-hit probability. Rejections include indicator evidence. No parameter may be promoted on an AI recommendation alone.

## Required experiment workflow

1. Gather contiguous, timestamped **closed** 1-hour and 4-hour USDⓈ-M candles and actual funding settlements for each configured symbol. Record listing dates, provider, observation times, hashes, missing bars and data range; do not synthesize missing candles.
2. Freeze strategy versions, scan timeframes, indicators, fees, target/stop order assumptions and rejection gates **before** evaluating the final holdout.
3. Evaluate each strategy separately and the combined arbitration/portfolio rules. Aggregate P&L across strategies only after simulating shared capital, conflicts and correlation. Never sum independent backtest profits and label them portfolio performance.
4. Run walk-forward splits with no leakage across folds and the required post-entry horizon embargo. Record out-of-sample net expectancy, win rate, drawdown, exposure, number of trades, signal frequency, profit factor and uncertainty.
5. Stress-test fees, slippage, funding, delayed fills, position sizing, lost candles, stop/target order within one candle, and model/threshold sensitivity.
6. Forward-test in shadow and Binance demo. Reconcile orders after uncertain network results and compare intended to actual fills before considering any separate live-readiness review.

## CLI examples

These commands require real historical data and are not claimed to have completed in the distributed package:

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
python -m backtest.evidence \
  --input research_data/walkforward_results.json \
  --output research_data/evidence_assessment.json
```

Dataset start dates must respect each contract's actual listing date and enough future holding-period candles for every test interval. Any `NOT_EVALUATED` or incomplete output blocks a review decision.

## Limitations and promotion gate

Replay cannot know tick-by-tick order of an intrabar stop and target without appropriate data. Research-level size and execution models are not fully equivalent to live portfolio accounting. No tested win rate, profitable expectancy or reliable TP-hit likelihood is asserted here.

A candidate for live review needs sufficient sample size, positive *net* holdout expectancy across distinct regimes, acceptable drawdown, stable results under realistic costs, documented data lineage, independent demo fills, and explicit operator approval. The research gate is a completeness/evidence record, not an automatic trading authorization. If evidence is insufficient, **no trade** is the correct outcome.
