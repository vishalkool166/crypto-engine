# Signal Engine 3.0 — implementation & deployment notes

This release extends the original self-hosted repo. It does **not** migrate
credentials, bypass original safety controls, or authorize real-money trading.

## Delivered

- The existing production EMA/ADX agent, Binance client, Telegram integration,
  public portal, operator login and execution-mode gates are retained.
- Four **separate research-only** candidates with deterministic rejection
  reasons: continuation, breakout-with-retest, range reversion and momentum
  reversal. `strategies/registry.py` cannot place orders.
- Shadow observations during eligible Binance candle scans, deduplicated by
  market, strategy and candle in SQLite.
- Strategy Lab research API and operator dashboard at `/strategy-lab`.
- Replay of closed 4-hour candles with next-open hypothetical fills, conservative
  stop-first resolution, notional cap, fees, slippage, holdout segregation and
  reproducible dataset fingerprints. Funding, order book and liquidation not
  modeled. **No research output is certified or promoted into trading**.
- Binance-only public futures market context (funding, open interest, global
  long/short ratios and top-account ratios). These are aggregated public
  indicators, **not** a feed of individual profitable trader positions.
- Private AI research records now include recent experiment and shadow data.
  Primary Groq model `openai/gpt-oss-20b`, alternate
  `openai/gpt-oss-120b`, no additional LLM provider subscription required.
- Portfolio drawdown snapshots now require signed `/fapi/v3/account`
  `totalMarginBalance` (includes unrealized P&L), never `cfg.CAPITAL` as equity.
  New openings halt if equity cannot be verified, is stale, or a risk circuit
  was triggered; old risk halts are deliberately not reset automatically.

## Credentials and Binance account

The provided repository contains `.env.example` placeholders, **no operational
`.env` or API secrets**. Deploy with the original server-side `.env` containing
`BINANCE_DEMO_API_KEY`, `BINANCE_DEMO_SECRET` for paper execution, and if
previously used, `BINANCE_API_KEY`, `BINANCE_SECRET` for live. **Never paste keys
into the ZIP or frontend**. Same variable names, same Binance futures routing.

The new Binance intelligence endpoints use public aggregate data without
Hyperliquid and without exposing your private account. If Binance blocks public
futures endpoints in your jurisdiction, values show unavailable.

The original controls still apply:

```
ENGINE_ENABLED=false
TRADING_MODE=paper
SIGNAL_ENGINE_ALLOW_LIVE_TRADING=
```

Leave the engine disabled while verifying database backup and account health.
Live mode requires an explicit operator opt-in, credentials, TOTP, account-flat
checks and restart workflow. Strategy Lab never authorizes live trading.

## Groq free model

`GROQ_MODEL=openai/gpt-oss-20b` is the default as of October 2026. The original
`llama-3.3-70b-versatile` was retired for free/developer-tier use in Aug 2026.
`GROQ_API_KEY` remains required, and the free tier has usage limits. Verify your
actual account's enabled models using:

```
python -m scripts.check_groq
```

This script runs a tiny real generation and prints only the model/response, never
keys. Without a deployed Groq key, model availability can be checked against
public documentation but not verified on your account. Free allowances change.

## Setup

1. Back up the existing SQLite database, `.env`, persistent runtime state and
   vector index before replacing the code.
2. Deploy the source tree, preserving those existing persistent assets.
3. Run `python -m pytest -q tests` after installing `requirements-dev.txt`.
4. Run `npm ci && npm run build` inside `dashboard/`. Deploy
   `dashboard/dist/public` and `dashboard/dist/admin` as before.
5. Start backend with `ENGINE_ENABLED=false`, verify database initialization,
   admin authentication, `/api/v1/admin/strategy-lab/registry`, and
   `/api/v1/admin/assistant/status`.
6. With valid Binance demo keys, verify v3 futures account equity and candle
   availability. Review circuit levels and existing trades; never force-reset a
   risk halt just to make a scan produce signals.
7. Use Strategy Lab to run replay (needs >=260 *cached closed* 4h candles),
   check shadow audit, and inspect futures aggregates. All results uncertified.
8. Perform full production validation separately before considering any real
   order permission. Adding modules is not proof of profitability.

## Research limitations / future work

The existing app caps cached 4h candles at 350 (~58 days). That is far too
short to establish a reliable edge or to evaluate rare setups. Use the original
separate walk-forward and funding-aware research pipeline with checksum-
verified multi-year data for rigorous validation. The Strategy Lab is a
**research preview**, not a replacement for that research gate.

The existing production agent has not been automatically replaced with the
four experimental strategies. This deliberate separation prevents untested
strategies from changing your trading behavior. Binance public aggregate data
is not personal wallet-level smart-money tracking; no Hyperliquid account is
required. Live Groq and Binance account validation requires your deployed
credentials and network access.
