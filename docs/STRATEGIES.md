# Strategy and decision reference

All four strategies run in the **main** Binance scanner through `strategies/pipeline.py`. They evaluate independently, share closed 4-hour market features, and are reconciled through one portfolio-risk/execution path. They are not four separately funded bots. The scanner also fetches 1-hour context; its four-strategy proposals are primarily based on the closed 4-hour feature set.

| Strategy ID | Opportunity hypothesis | Structural invalidation / exit hypothesis |
| --- | --- | --- |
| `trend_continuation` | Follow established trend alignment with momentum/pullback confirmation. | Stop beyond a recent directional structure with ATR buffer; target nearby historical opposing structure. |
| `breakout_retest` | Confirm range or level breakout with supporting candle/volume conditions. | Stop beyond invalidated breakout boundary; target opposing prior structure, or measured prior range where no comparable level is present. |
| `range_reversion` | Evaluate a sufficiently defined sideways range for mean reversion. | Stop outside prior range structure; target constrained by the range midpoint and opposing levels. |
| `momentum_reversal` | Look for reversal confirmation after directional exhaustion. | Stop beyond observed local extreme; target prior opposing structure. |

These are **candidate rules**, not documented winning strategies. Structural levels are derived from historical closed candles, not a live order book or a validated forecast of where price will trade. ATR remains a volatility buffer; the engine rejects proposals without viable positive structural reward and applies additional per-coin reward/risk constraints.

## Shared evaluation

`strategies/registry.py` computes EMA 20/50/200, RSI, ADX, ATR, volume ratio, range bounds and prior high/low features. A minimum of 220 sorted, valid, closed candles is required for evaluation. Each decision records named checks as `{name, actual, required, passed}` alongside a rejection reason or proposed trade. Observations written before this contract may lack details; do not substitute invented historical values.

`strategies/pipeline.py` translates candidates to the existing sizing contract. A heuristic score is **not** a calibrated probability of profit. Opposing eligible proposals for the same coin are rejected. Multiple same-direction candidates do not automatically create multiple positions. Market regime informs eligibility, but a strategy remains responsible for its own decision.

## Trade lifecycle and permissions

The Strategy Board provides per-strategy **Scan** and **Execute** controls stored in application state. Scanning records assessments; execution additionally requires eligibility, central risk approval and the active account mode. Paper mode targets Binance demo credentials; live mode is a separately guarded operation that can submit real orders. An update does not silently switch modes.

An `evaluated_no_setup` status indicates that the scanner assessed a symbol and found no qualified proposal. `scan_error`, `stale_scan`, insufficient data and cooldown/position states must remain distinguishable. Pending signals older than the configured expiry policy are made non-actionable but remain in records for auditing.

## Reading a rejected decision

Review the strategy, symbol, observation time and regime, then inspect every individual check's actual value, requirement and pass/fail outcome. For example, a trend setup rejected in a transitional regime should not be described as an exchange connectivity problem. Missing checks on an older stored observation indicate missing historical evidence, not a failed indicator.

## Limits

- Four strategies share many inputs and account exposure; they are not statistically independent sources of returns.
- Historical backtests cannot prove fill probabilities or future profitability.
- A geometrically reachable price is not automatically a probable or attractive trade after fees, slippage and funding.
- Settings and thresholds have not been certified across the 18-coin universe. See [Research](RESEARCH.md) and [Research gate](RESEARCH_GATE.json).
