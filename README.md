# Signal Engine v5

Automated crypto signal intelligence engine built on Binance Futures.
Combines ICT concepts, multi-timeframe confluence scoring, and smart money principles
into a fully automated trading system with real-time dashboard, Telegram control,
Twitter content pipeline, and LightGBM ML gate.

Execution is handled by Freqtrade. Signal Engine is the brain.
Redis is the shared nervous system between them.

---

## Architecture

```
Binance API
↓
Freqtrade (execution body)
Fetches: OHLCV, ticker, funding, OI, long/short ratio
Pushes all data to Redis
↓
Redis (shared data layer)
↓
Signal Engine (signal brain)
Reads market data from Redis
Generates signals using confluence engine
Writes signals back to Redis
↓
Freqtrade reads signals from Redis
Freqtrade executes trades on Binance
↓
Signal Engine syncs outcomes from Freqtrade
LightGBM trains on closed signal data (after 100 trades)
```

---

## What It Does

- Scans dynamic coin universe across 4 timeframes every 15 minutes
- Scores each coin using 16 weighted confluence factors
- Grades signals A+, A, B based on market and entry quality
- Forwards A+/A signals to Freqtrade for execution via Redis
- B grade signals execute in paper mode only with quality filter
- ML gate filters signals by win probability after 100 closed trades
- Generates Twitter content for every A+/A signal with Telegram approval
- Generates market commentary posts during no-signal scans
- Sends real-time Telegram alerts with full trade thesis
- Displays live dashboard with Freqtrade trade data
- Runs full backtests with walk-forward simulation
- Tracks factor performance across all closed trades
- Syncs Freqtrade trade outcomes back to Signal table for ML training

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Execution | Freqtrade (separate container) |
| Data Layer | Redis 7 |
| Database | SQLite via SQLAlchemy |
| Exchange | Binance Futures via CCXT |
| Scheduling | APScheduler |
| Indicators | TA-Lib (ta), Pandas, NumPy |
| ML | LightGBM + scikit-learn |
| Alerts | Telegram Bot API via HTTPX |
| Content | Groq (llama-3.3-70b), mplfinance, tweepy |
| Frontend | Vanilla JS, TailwindCSS, Chart.js |
| Infrastructure | Docker, nginx, AWS EC2 |
| Auto-deploy | Git cron watcher |

---

## Project Structure

```
/
├── crypto-engine/
│   ├── main.py                    # FastAPI app, WebSocket, lifespan
│   ├── config.py                  # Configuration, weights, constants
│   ├── database.py                # SQLAlchemy models, session management
│   ├── scheduler.py               # APScheduler — scan, briefing, ML, sync
│   ├── redis_client.py            # Redis connection singleton
│   ├── requirements.txt
│   │
│   ├── engines/                   # Signal intelligence — untouched core
│   │   ├── signal.py              # Signal generation, grading, B-grade filter
│   │   ├── confluence.py          # 16-factor weighted confluence scorer
│   │   ├── sweep.py               # Liquidity sweep detection
│   │   ├── displacement.py        # Displacement/impulse detection
│   │   ├── retest.py              # Retest zone confirmation
│   │   ├── regime.py              # Market regime detection
│   │   ├── indicators.py          # All technical indicators
│   │   ├── orderblocks.py         # ICT order block detection
│   │   ├── thesis.py              # Trade thesis and explanation builder
│   │   └── validator.py           # Candle data validation and cleaning
│   │
│   ├── alerts/
│   │   ├── scanner.py             # Coin analysis orchestrator, scan loop
│   │   ├── telegram.py            # Bot commands, webhook, signal alerts
│   │   ├── briefing.py            # Morning/evening briefing
│   │   └── utils.py               # Shared alert utilities
│   │
│   ├── trade/
│   │   ├── sync.py                # Freqtrade outcome sync to Signal table
│   │   └── state.py               # Compatibility stub
│   │
│   ├── ml/
│   │   ├── eligibility.py         # ML readiness check, auto-train trigger
│   │   ├── dataset.py             # Feature matrix builder from Signal table
│   │   ├── trainer.py             # LightGBM training, model persistence
│   │   └── predictor.py           # Win probability prediction
│   │
│   ├── content/
│   │   ├── pipeline.py            # Content orchestrator, commentary trigger
│   │   ├── chart_engine.py        # mplfinance signal chart generator
│   │   ├── groq_writer.py         # Groq social post draft generator
│   │   ├── approval_flow.py       # Telegram approve/discard/edit flow
│   │   └── publisher.py           # Twitter API poster, engagement tracker
│   │
│   ├── data/
│   │   ├── fetcher.py             # Redis-first data fetcher with Binance fallback
│   │   ├── store.py               # Candle persistence to SQLite
│   │   └── cache.py               # In-memory TTL cache
│   │
│   ├── api/
│   │   ├── routes.py              # All REST API endpoints
│   │   ├── freqtrade.py           # Freqtrade API proxy endpoints
│   │   └── formatters.py          # Dashboard payload builders
│   │
│   ├── backtest/
│   │   ├── engine.py              # Walk-forward backtest simulation
│   │   ├── report.py              # Backtest report builder
│   │   └── factor_analysis.py     # Factor edge analysis
│   │
│   ├── nginx/
│   │   └── signal-engine.conf     # Nginx site config
│   │
│   └── frontend/
│       ├── index.html             # Single page dashboard
│       ├── login.html             # Login page
│       ├── setup.html             # First-run TOTP setup
│       ├── css/app.css            # Apple-style design system
│       └── js/
│           ├── api.js             # HTTP fetch, Freqtrade API calls
│           ├── websocket.js       # Dashboard WebSocket handler
│           ├── render.js          # All DOM render functions
│           ├── ui.js              # Helpers, toast, color, format
│           ├── state.js           # Client state, clock, countdown
│           ├── charts.js          # Equity curve, PnL bar chart
│           └── modal.js           # Coin detail modal, signal detail
│
├── freqtrade/
│   └── user_data/
│       ├── config.json            # Freqtrade configuration
│       ├── start.sh               # Startup script with redis install
│       └── strategies/
│           └── SignalEngineStrategy.py  # Reads signals from Redis, executes
│
└── docker-compose.yml             # Full stack orchestration
```

---

## Signal Grading System

| Grade | Score | Action | Mode |
|-------|-------|--------|------|
| A+ | 85-100 | Auto-execute | Paper + Live |
| A | 68-84 | Auto-execute | Paper + Live |
| B | 52-67 | Execute with quality filter | Paper only |
| C | 38-51 | Watch — setup building | Never |
| F | 0-37 | Hard block | Never |

### Grade B Quality Filter
B grades only execute in paper mode when ALL of these pass:
- Market score >= 65
- London or NY session (not Asia, not Off Hours)
- BTC score >= 4 (not strongly conflicting)
- Maximum 1 hard block (session block acceptable)

### Grade-Aware Risk and TP
| Grade | Risk % | TP Multiplier |
|-------|--------|--------------|
| A+ | 2% of capital | 2.5x risk distance |
| A | 1.5% of capital | 2.0x risk distance |
| B | 1% of capital | 1.5x risk distance |

Single TP only — no TP1/TP2 split.
TP placed at nearest structure OR grade multiplier, whichever is closer.

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

## ML Gate

LightGBM binary classifier trained on closed signal data.

**Features:** All 16 factor scores + regime + session + sweep/retest/disp scores + BTC score + funding + grade

**Label:** win=1 loss=0

**Activation:** Auto-trains when 100 closed trades exist in Signal table

**Behavior:**
- Below 100 trades: all A+/A/B signals forwarded to Freqtrade
- After 100 trades: signals with win probability < 0.65 filtered out
- Retrains every 50 new trades automatically
- Telegram notification sent when model trains

---

## Content Pipeline

Triggered automatically for every A+/A signal.

```
Signal generated
↓
Chart generated (mplfinance 4H candlestick with levels)
↓
Groq writes post draft (professional/educational/humor rotation)
↓
Telegram sends you chart + draft with 4 buttons:
  ✅ Approve & Post → posts to Twitter
  ❌ Discard
  ✏️ Edit Draft → you type new text
  🔄 Regenerate → new Groq draft
```

**Commentary posts** generated when scan finds no tradeable signals.
Triggered by: choppy market, extreme fear/greed, extreme funding, weekend.
Cooldown: 1h London/NY overlap, 2h London/NY, 6h Asia, 8h weekend.

**Tone rotation:**
- Signal posts: 70% professional, 20% educational, 10% humor
- Commentary posts: 40% humor, 30% educational, 30% professional

---

## Freqtrade Integration

Signal Engine writes signals to Redis. Freqtrade reads them.

**Redis keys written by Freqtrade:**
```
candles:{coin}USDT:{tf}    OHLCV data, TTL 900s
ticker:{coin}USDT          Price + 24h change, TTL 60s
funding:{coin}USDT         Funding rate, TTL 300s
oi:{coin}USDT              Open interest, TTL 300s
oi_change:{coin}USDT       OI change %, TTL 300s
ls_ratio:{coin}USDT        Long/short ratio, TTL 300s
```

**Redis keys written by Signal Engine:**
```
signal:{coin}USDT          Full signal payload, TTL 900s
pairs:active               Active coin list for Freqtrade pairlist
```

**Outcome sync:**
Scheduler runs every 30 minutes.
Reads Freqtrade closed trades via API.
Matches to Signal table by coin + entry price + timestamp.
Updates Signal.outcome, Signal.pnl, Signal.exit_price.
This feeds the ML training pipeline.

---

## SL Calculation — Structure-Aware

SL placed at actual trade invalidation point.

**Priority order:**
1. Below retest zone bottom + ATR×0.15 buffer
2. Below sweep low + ATR×0.1 buffer
3. Beyond swing point + ATR×0.1 buffer
4. ATR × regime multiplier fallback

**ATR Multiplier by Regime:**
| Regime | Multiplier |
|--------|-----------|
| Expansion | 2.5x |
| Trending | 2.0x |
| Weak Trend | 1.5x |

---

## Database Schema

### Signal
Every signal generated with full confluence context.
Outcome updated by sync job after Freqtrade closes trade.

### Trade
Compatibility stub — Freqtrade owns trade execution and storage.

### Candle
Persistent OHLCV storage for all coins and timeframes.

### ContentPost
Every Twitter post with draft, status, tweet ID, engagement metrics.

### CoinConfig
Dynamic coin universe — add/remove via dashboard or API.

### AuditLog
All mode changes, coin additions, manual closes.

### BacktestResult
Backtest run history for comparison.

---

## Scan Schedule

| Job | Schedule | Description |
|-----|----------|-------------|
| Coin scan | :00/:15/:30/:45 UTC | Full coin universe analysis |
| Morning briefing | 08:00 UTC (13:30 IST) | London open market summary |
| Evening briefing | 13:00 UTC (18:30 IST) | NY open market summary |
| Outcome sync | Every 30 minutes | Freqtrade → Signal table sync |
| ML check | Every 1 hour | Auto-train when 100 trades ready |
| Engagement update | Every 6 hours | Twitter metrics refresh |

---

## Trading Modes

| Mode | Grades | Freqtrade | Real Money |
|------|--------|-----------|-----------|
| Paper | A+, A, B | dry_run: true | No |
| Live | A+, A only | dry_run: false | Yes |

**Mode switching:**
- Requires TOTP verification
- Blocked if any trades are open
- Updates Freqtrade config.json automatically
- Restarts Freqtrade container automatically
- Toggle button on dashboard header

---

## Setup

### Requirements
- AWS EC2 (t3.small minimum, t3.medium recommended)
- Docker + Docker Compose
- Binance Futures account
- Telegram bot token
- Finnhub API key (free tier)
- Groq API key (free tier)
- Twitter/X Basic API ($100/month) — optional for content posting

### Environment Variables

```env
BINANCE_API_KEY=
BINANCE_SECRET=
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
FINNHUB_KEY=
GROQ_API_KEY=
DOMAIN=https://signal-engine-v5.vishalkool.top
PORT=8000
ENV=production
CAPITAL=1000
REDIS_URL=redis://redis:6379
FREQTRADE_URL=http://freqtrade:8080
FREQTRADE_USERNAME=
FREQTRADE_PASSWORD=
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_SECRET=
CONTENT_ENABLED=True
CONTENT_AUTO_APPROVE=False
```

### Deploy

```bash
git clone <repo>
cd crypto-engine
docker compose up --build -d
```

Auto-deploy via cron:
```bash
crontab -e
# Add:
* * * * * /home/ubuntu/update.sh >> /home/ubuntu/update.log 2>&1
```

---

## API Endpoints

### Signal Engine
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard` | GET | Full dashboard payload |
| `/api/analyze/{coin}` | GET | Single coin analysis |
| `/api/scan` | GET | Trigger full scan |
| `/api/signals` | GET | Signal history |
| `/api/signals/latest` | GET | Latest valid Redis signal |
| `/api/signals/active` | GET | All valid Redis signals |
| `/api/stats` | GET | All time statistics |
| `/api/coins` | GET | Coin universe |
| `/api/coins/active` | GET | Active pairs for Freqtrade |
| `/api/coins/add` | POST | Add coin |
| `/api/coins/toggle` | POST | Enable/disable coin |
| `/api/coins/{coin}` | DELETE | Remove coin |
| `/api/market/{coin}` | GET | Market data |
| `/api/fear-greed` | GET | Fear and greed index |
| `/api/backtest/{coin}` | GET | Run backtest |
| `/api/analysis/factors` | GET | Factor analysis |
| `/api/sync/outcomes` | POST | Manual outcome sync |
| `/api/mode/toggle` | POST | Switch live/paper with TOTP |
| `/api/mode/status` | GET | Current mode |
| `/api/health` | GET | System health + ML status |
| `/api/audit/log` | GET | Audit log |

### Freqtrade Proxy
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ft/summary` | GET | Status + profit + balance + config |
| `/api/ft/status` | GET | Open trades |
| `/api/ft/profit` | GET | Profit summary |
| `/api/ft/balance` | GET | Account balance |
| `/api/ft/start` | POST | Start bot |
| `/api/ft/stop` | POST | Stop bot |
| `/api/ft/forcesell` | POST | Force close trade |

---

## WebSocket

| Endpoint | Description |
|----------|-------------|
| `/ws/dashboard` | Dashboard push every 5 seconds on change |

---

## Telegram Commands

### Status
| Command | Description |
|---------|-------------|
| `/status` | Bot status, coins, last scan |
| `/mode` | Current configuration |
| `/next` | Next scan and session times |
| `/session` | Current session quality |

### Market
| Command | Description |
|---------|-------------|
| `/btc` | BTC analysis |
| `/coin ETH` | Any coin analysis with ML probability |
| `/regime` | Regime across all coins |
| `/funding` | Funding rates |
| `/fear` | Fear and greed index |

### Signals
| Command | Description |
|---------|-------------|
| `/scan` | Trigger manual scan |
| `/queue` | Best signal in cache |
| `/brief` | Morning briefing (London open) |
| `/evening` | Evening briefing (NY open) |

### Performance
| Command | Description |
|---------|-------------|
| `/pnl` | All time PnL |
| `/history` | Last 5 signals with IST timestamps |
| `/stats` | Full stats by grade A+/A/B |
| `/streak` | Win/loss streak |
| `/grade` | Grade accuracy breakdown |
| `/daily` | Daily summary |

### Analysis
| Command | Description |
|---------|-------------|
| `/backtest BTC` | Backtest a coin |
| `/factors` | Factor edge analysis |
| `/debrief` | Last signal debrief |

### ML
| Command | Description |
|---------|-------------|
| `/ml` | ML model status and progress |
| `/sync` | Manual Freqtrade outcome sync |

### Freqtrade
| Command | Description |
|---------|-------------|
| `/ftstatus` | Open trades with PnL |
| `/ftbalance` | Account balance |
| `/ftprofit` | Profit summary |
| `/ftstart` | Start Freqtrade bot |
| `/ftstop` | Stop Freqtrade bot |

### Content
| Command | Description |
|---------|-------------|
| `/pending` | Posts awaiting approval |
| `/content` | Posting stats and engagement |

---

## Infrastructure

```
AWS EC2 t3.small (2 vCPU, 2GB RAM)
├── nginx (system service)
│   ├── signal-engine-v5.vishalkool.top → signal-engine:8000
│   └── freqtrade.vishalkool.top → freqtrade:8080
│
└── Docker Compose
    ├── redis (redis:7-alpine)
    ├── signal-engine (custom build)
    └── freqtrade (freqtradeorg/freqtrade:stable)
```

**Resource usage (approximate):**
| Service | RAM |
|---------|-----|
| Signal Engine | ~400MB |
| Freqtrade | ~350MB |
| Redis | ~50MB |
| OS + nginx | ~150MB |
| Total | ~950MB / 2GB |

---

## Known Design Decisions

| Decision | Reason |
|----------|--------|
| Freqtrade for execution | Battle-tested, handles order management, reconciliation |
| Redis as data layer | Freqtrade pushes market data, Signal Engine reads it — no duplicate API calls |
| Single TP per trade | Cleaner ML training labels — full win or full loss |
| Grade B paper only | Collect data without real risk — ML learns which B grades actually win |
| Dynamic coin universe | Add/remove coins via dashboard without code changes |
| TOTP for mode switch | Prevents accidental live mode activation |
| Block switch if trades open | Prevents orphaned positions on Binance |
| Outcome sync job | Freqtrade and Signal Engine have separate DBs — sync bridges them |

---

## Limitations

| Limitation | Notes |
|-----------|-------|
| t3.small RAM | 15+ coins may cause memory pressure during scans |
| No order book | Microstructure data not used — 15min timeframe does not need it |
| SQLite | Sufficient for single instance — PostgreSQL needed for scale |
| Freqtrade dry_run | Paper balance is simulated $1000 — not real account balance |
| ML needs 100 trades | Factor analysis unreliable below this threshold |
| Twitter Basic tier | $100/month — 1500 tweets/month limit |
| No tick data | CVD approximated from OHLCV |

---

## Performance Expectations

No system guarantees profitability.
Signal quality improves with sample size and market condition alignment.
Minimum 100 closed trades before ML activates.
Minimum 200 closed trades before factor analysis is statistically reliable.
Run paper trading for at least 3 months before evaluating edge.

---

## Version

Signal Engine v5
Built with Python + FastAPI + Freqtrade + Redis + LightGBM and a lot of market structure reading.