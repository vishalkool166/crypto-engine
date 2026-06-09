# Signal Engine v5

Automated crypto signal detection and trade execution engine built on Binance Futures.
Combines ICT concepts, multi-timeframe confluence scoring, and smart money principles
into a fully automated paper trading system with real-time dashboard and Telegram control.

---

## What It Does

- Scans 13 crypto coins across 4 timeframes every 15 minutes
- Scores each coin using 16 weighted confluence factors
- Grades signals A+, A, B, C, F based on market and entry quality
- Auto-executes A/A+ signals with full risk management
- Monitors active trades with health engine — BOS, CHoCH, OB invalidation
- Sends real-time Telegram alerts with full trade thesis
- Displays live dashboard with WebSocket price feed
- Runs full backtests with walk-forward simulation
- Tracks factor performance across all closed trades

---

## Coins Covered

**Tier 1:** BTC, ETH, BNB, SOL, XRP

**Tier 2:** ADA, AVAX, LINK, DOT, DOGE, LTC, ATOM, POL

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Database | SQLite via SQLAlchemy |
| Exchange | Binance Futures via CCXT |
| Scheduling | APScheduler |
| Indicators | TA-Lib (ta), Pandas, NumPy |
| Alerts | Telegram Bot API via HTTPX |
| Frontend | Vanilla JS, TailwindCSS, Chart.js |
| Tunnel | ngrok (custom domain) |
| Auto-deploy | Git polling watcher |

---

## Project Structure

```
crypto-engine/
├── main.py                    # FastAPI app, WebSocket handlers, lifespan
├── config.py                  # All configuration, weights, constants
├── database.py                # SQLAlchemy models, session management
├── scheduler.py               # APScheduler jobs — scan, monitor, briefing
├── watcher.py                 # Auto-restart, git polling, ngrok tunnel
├── requirements.txt
│
├── engines/
│   ├── signal.py              # Signal generation, grading, no-trade engine
│   ├── confluence.py          # 16-factor weighted confluence scorer
│   ├── sweep.py               # Liquidity sweep detection
│   ├── displacement.py        # Displacement/impulse detection
│   ├── retest.py              # Retest zone confirmation
│   ├── regime.py              # Market regime detection
│   ├── health.py              # Trade health monitoring
│   ├── indicators.py          # All technical indicators
│   ├── orderblocks.py         # ICT order block detection
│   ├── thesis.py              # Trade thesis and explanation builder
│   └── validator.py           # Candle data validation and cleaning
│
├── alerts/
│   ├── scanner.py             # Coin analysis orchestrator, scan loop
│   ├── telegram.py            # Bot commands, webhook, signal alerts
│   ├── briefing.py            # Morning briefing, post-trade debrief
│   └── utils.py               # Shared alert utilities
│
├── trade/
│   ├── manager.py             # Trade lifecycle — open, monitor, close
│   ├── state.py               # Trade state machine, daily risk tracking
│   ├── orders.py              # Paper order store, order management
│   ├── risk.py                # Risk guard, position sizing, pre-trade checks
│   └── price_feed.py          # Binance WebSocket price stream
│
├── data/
│   ├── fetcher.py             # CCXT data fetcher, fear/greed, news filter
│   ├── store.py               # Candle persistence to SQLite
│   └── cache.py               # In-memory TTL cache with price invalidation
│
├── api/
│   ├── routes.py              # All REST API endpoints
│   └── formatters.py          # Dashboard payload builders, color helpers
│
├── backtest/
│   ├── engine.py              # Walk-forward backtest simulation
│   ├── report.py              # Backtest report builder
│   └── factor_analysis.py     # Factor edge analysis from closed trades
│
└── frontend/
    ├── index.html             # Single page dashboard
    ├── css/app.css            # Apple-style design system
    └── js/
        ├── api.js             # HTTP fetch, scan trigger, close trade
        ├── websocket.js       # WS price feed, dashboard push handler
        ├── render.js          # All DOM render functions
        ├── ui.js              # Helpers, toast, color, format functions
        ├── state.js           # Client state, clock, countdown
        ├── charts.js          # Equity curve, PnL bar chart
        └── modal.js           # Coin detail modal, close confirmation
```

---

## Signal Grading System

| Grade | Score | Action |
|-------|-------|--------|
| A+ | 85-100 | Full signal — auto-execute |
| A | 68-84 | Full signal — auto-execute |
| B | 52-67 | Skip — below minimum |
| C | 38-51 | Watch — setup building |
| F | 0-37 | Hard block — stay out |

---

## Confluence Factors — 16 Weighted

| Factor | Weight | What It Checks |
|--------|--------|---------------|
| Liquidity Sweep | 12 | Stop hunt at key level confirmed |
| Retest Confirmation | 12 | Price returned to OB/FVG/EMA zone |
| Displacement | 11 | Impulsive move away from zone |
| Market Regime | 10 | Trending/ranging/expansion detection |
| Weekly Filter | 10 | Weekly and daily trend alignment |
| Market Structure | 9 | BOS/CHoCH structure bias |
| Session Timing | 8 | London/NY/Overlap quality |
| BTC Alignment | 8 | BTC 1D and 4H trend confirmation |
| OI Behavior | 7 | Open interest confirming direction |
| Volume Expansion | 7 | Volume above MA on signal candle |
| Funding Extreme | 6 | Funding rate squeeze risk filter |
| RSI Divergence | 4 | Hidden/regular divergence on 4H |
| Order Blocks | 4 | ICT OB zone proximity and strength |
| ATR Volatility | 3 | Volatility within tradeable range |
| RSI Context | 2 | RSI not overbought/oversold extreme |
| MACD Histogram | 1 | Histogram expanding in direction |

---

## SL/TP Calculation — Structure-Aware

### Stop Loss
SL is placed at the actual trade invalidation point — not a mechanical ATR multiple.

**Priority order:**
1. Below retest zone bottom + ATR×0.15 buffer (actual invalidation)
2. Below sweep low (where smart money acted)
3. Beyond swing point (structural invalidation)
4. ATR × regime multiplier fallback

**ATR Multiplier by Regime:**
| Regime | Multiplier |
|--------|-----------|
| Expansion | 2.5x |
| Trending | 2.0x |
| Weak Trend | 1.5x |

### Take Profit
TP levels are placed at real market structure — not fixed R multiples.

**TP1:** Nearest resistance/support from swing highs/lows, PDH/PDL, VAH from volume profile

**TP2:** Next major structure from weekly levels, PWH/PWL, POC

### Trade Management
- 70% of position targets TP1
- 30% of position targets TP2
- On TP1 hit — SL moves to breakeven automatically
- Remaining 30% runs risk-free to TP2

---

## Risk Management

| Parameter | Value |
|-----------|-------|
| Capital | Configurable via .env |
| Leverage | 10x |
| Risk per trade | 10% of capital (dynamic 7-13% by score) |
| Daily loss cap | 20% of capital |
| Max trades per day | 3 |
| Min grade to trade | A+ and A |

### Dynamic Risk Sizing
Risk percentage scales with signal confidence score:
- Score 95+ → 13% risk
- Score 85-94 → 10-13% risk
- Score 68-84 → 7-10% risk

---

## Trade Health Engine

Monitors active trade continuously every 1 minute.

| State | Meaning |
|-------|---------|
| HEALTHY | All thesis conditions intact |
| WARNING | One or more conditions weakening |
| INVALIDATED | Thesis broken — consider closing |

**Checks performed:**
- Retest zone holding or broken
- BOS/CHoCH against trade direction
- Daily structure bias flip
- BTC alignment change
- OI exhaustion signal
- Price adverse move vs ATR
- Order block mitigation status

**Debounce:** State changes require 120 seconds persistence before alerting — prevents noise.

---

## Database Schema

### Signal
Stores every A/A+ signal generated with full context.

| Key Fields | Description |
|-----------|-------------|
| grade, score | Signal quality |
| entry, sl, tp1, tp2 | Price levels |
| sweep_score, retest_score, disp_score | Engine scores |
| factor_scores | JSON of all 16 factor scores at signal time |
| market_score, entry_score | Market vs entry quality split |
| atr_at_entry | Volatility context |
| btc_score | BTC alignment at signal time |
| regime, session | Market context |
| outcome, exit_price, pnl | Result tracking |

### Trade
Stores every executed trade with full lifecycle data.

| Key Fields | Description |
|-----------|-------------|
| entry_price, sl_price, tp1_price, tp2_price | Levels used |
| position_size, margin_used, leverage | Sizing |
| tp1_hit | Whether TP1 was reached |
| partial_pnl | PnL from TP1 portion separately |
| regime_at_entry, session_at_entry, score_at_entry | Context |
| health_at_close | Health state when trade closed |
| outcome, pnl, close_reason | Result |

### DailyRisk
Tracks daily trade count, PnL, loss, and cap status.

### Candle
Persistent OHLCV storage for all coins and timeframes.

### BacktestResult
Stores backtest run results for historical comparison.

---

## Backtest Engine

Walk-forward simulation on historical candle data.

**How it works:**
- Slides 200-candle window across full history
- Runs full signal engine on each window
- Simulates trade on future 4H candles
- Tracks TP1→BE→TP2 logic accurately
- Applies taker fee both sides (0.06%)
- Reports by grade, regime, session, phase

**Metrics produced:**
- Win rate overall and by grade
- Total PnL and return percentage
- Profit factor
- Max drawdown
- Expectancy per trade
- Phase breakdown — TP1 vs TP2 vs SL vs timeout
- Regime breakdown — trending vs ranging vs expansion
- Session breakdown — London vs NY vs overlap

---

## Factor Analysis

Observes which confluence factors correlate with winning trades.
Requires 200+ closed trades for statistically reliable conclusions.

Uses actual stored factor scores — not proxies.
Produces edge table showing which factors add real value.

---

## Setup

### Requirements
- Python 3.11+
- ngrok account with custom domain
- Binance Futures account (paper trading — no real funds needed)
- Telegram bot token
- Finnhub API key (free tier sufficient)

### Installation

```bash
git clone <repo>
cd crypto-engine
pip install -r requirements.txt
```

### Environment Variables

Create `.env` file in root:

```
BINANCE_API_KEY=your_key
BINANCE_SECRET=your_secret
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
FINNHUB_KEY=your_finnhub_key
DOMAIN=https://your-ngrok-domain.ngrok-free.app
PORT=8000
ENV=development
CAPITAL=10
```

### Run

```bash
# Windows
start.bat

# Direct
python watcher.py
```

Watcher handles:
- Starting ngrok tunnel
- Installing requirements
- Starting the app
- Auto-restarting on git changes
- ngrok tunnel health monitoring

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard` | GET | Full dashboard payload |
| `/api/analyze/{coin}` | GET | Single coin analysis |
| `/api/scan` | GET | Trigger full scan |
| `/api/signals` | GET | Signal history |
| `/api/stats` | GET | All time statistics |
| `/api/trade/status` | GET | Active trade status |
| `/api/trade/close` | POST | Manual close |
| `/api/trade/history` | GET | Closed trade history |
| `/api/risk/daily` | GET | Daily risk state |
| `/api/market/{coin}` | GET | Market data for coin |
| `/api/fear-greed` | GET | Fear and greed index |
| `/api/backtest/{coin}` | GET | Run backtest |
| `/api/analysis/factors` | GET | Factor analysis |
| `/api/health` | GET | System health check |

---

## WebSocket Endpoints

| Endpoint | Description |
|----------|-------------|
| `/ws/price` | Live price feed for active trade |
| `/ws/dashboard` | Dashboard push every 3 seconds on change |

---

## Telegram Commands

### Trade
| Command | Description |
|---------|-------------|
| `/status` | Trade state and health |
| `/thesis` | Why this trade exists |
| `/health` | Full health engine output |
| `/levels` | Price ladder and progress |
| `/close` | Close with confirmation |

### Market
| Command | Description |
|---------|-------------|
| `/btc` | BTC analysis |
| `/coin ETH` | Any coin analysis |
| `/regime` | Regime across Tier 1 |
| `/funding` | Funding rates all coins |
| `/fear` | Fear and greed index |

### Performance
| Command | Description |
|---------|-------------|
| `/pnl` | Today and all time PnL |
| `/history` | Last 5 closed trades |
| `/stats` | Full all time statistics |
| `/streak` | Win and loss streak |
| `/grade` | Grade accuracy breakdown |

### Risk and Session
| Command | Description |
|---------|-------------|
| `/risk` | Daily risk state |
| `/session` | Current session quality |
| `/daily` | Daily summary |
| `/next` | Next scan and session times |

### Bot Control
| Command | Description |
|---------|-------------|
| `/scan` | Trigger manual scan |
| `/queue` | Best signal with approve/skip |
| `/pause` | Pause auto-execution |
| `/resume` | Resume auto-execution |
| `/mode` | Current configuration |
| `/brief` | Morning briefing now |

### Analysis
| Command | Description |
|---------|-------------|
| `/backtest BTC` | Backtest a coin |
| `/factors` | Factor edge analysis |
| `/debrief` | Last trade debrief |
| `/help` | Full command reference |

---

## Scan Schedule

| Job | Schedule | Description |
|-----|----------|-------------|
| Coin scan | :00/:15/:30/:45 UTC | Full 13-coin analysis |
| Trade monitor | Every 1 minute | Health check on active trade |
| Morning briefing | 08:00 IST daily | Market summary via Telegram |

---

## Paper Trading Mode

All trades are simulated — no real funds used.

| Feature | Implementation |
|---------|---------------|
| Order store | Persistent JSON file |
| Entry fills | Market price at signal time |
| SL/TP triggers | Price comparison on each tick |
| Fee simulation | 0.06% taker both sides |
| Backup | Auto-backup on every save |
| Recovery | Restores from backup on corruption |

On restart with active trade — orders are reconciled against DB.
Missing orders are recreated automatically with Telegram alert.

---

## Known Design Decisions

| Decision | Reason |
|----------|--------|
| Single trade at a time | Eliminates correlation risk entirely |
| Paper trading only | Safe for development and learning |
| SQLite database | Sufficient for single-instance bot |
| Sequential scan with Semaphore(3) | Respects Binance request weight limits |
| 15-minute scan interval | Balances freshness with API usage |
| A/A+ only auto-execute | Strict quality gate — no marginal trades |

---

## Operational Notes

### Binance API Weight
Scan uses Semaphore(3) — maximum 3 coins analyzed concurrently.
Stays well within Binance 2400 weight/minute limit.
Weight usage logged via X-MBX-USED-WEIGHT header.

### ngrok Tunnel
Tunnel health checked every 5 minutes by watcher.
Auto-restarts if tunnel drops.
Telegram webhook re-registered on tunnel restart.

### Database
WAL journal mode enabled — prevents corruption on crash.
All timestamps use timezone-aware UTC.

### Notifications
- 80% daily loss cap warning sent proactively
- Heartbeat alert if no signal found for 3+ hours
- Binance API failure alerts after repeated errors
- Finnhub unavailability warning

---

## Limitations

| Limitation | Notes |
|-----------|-------|
| Paper trading only | Live trading requires additional order management |
| Single trade | No portfolio mode |
| $10 default capital | Fees are significant percentage at small capital |
| 200+ trades needed | Factor analysis unreliable below this threshold |
| No tick data | CVD is approximated from OHLCV |
| Backtest has no slippage | Live results will differ |

---

## Performance Expectations

No system guarantees profitability.
Signal quality improves with sample size and market condition alignment.
Minimum 200 closed trades before drawing statistical conclusions.
Run paper trading for at least 3-6 months before evaluating edge.

---

## Version

Signal Engine v5 — hobby project
Built with Python, FastAPI, and a lot of market structure reading.
```