# How Signal Engine v5 Works — Complete Technical Deep Dive

<div align="center">

*A step-by-step walkthrough of how Signal Engine v5 thinks, decides, and acts across two markets — crypto futures and Indian equity.*

[![Live System](https://img.shields.io/badge/🔴_LIVE-Running_24%2F7-00ff88?style=for-the-badge)](https://signal-engine-v5.vishalkool.top)

</div>

---

## 🧠 The Big Picture

```
Two completely separate trading strategies
running on the same infrastructure:

CRYPTO ENGINE                    INDIAN ENGINE
─────────────                    ─────────────
Binance Futures                  AngelOne (NSE)
37 coins                         BANKNIFTY + FINNIFTY
Every 15 minutes                 Once per day
ADX + RSI + Volume scoring       ORB breakdown strategy
LangGraph agent pipeline         Rule-based entry logic
Paper + Live execution           Paper tracking

Both feed into:
  → Same Redis layer
  → Same SQLite database
  → Same Telegram bot
  → Same React dashboard
  → Same RAG intelligence layer
  → Same LangSmith observability
```

---

## ⏱️ The Crypto Scan Cycle

```
UTC Clock
    │
    ├── :00 ──► CRYPTO SCAN FIRES
    ├── :15 ──► CRYPTO SCAN FIRES
    ├── :30 ──► CRYPTO SCAN FIRES + RAG REINDEX
    └── :45 ──► CRYPTO SCAN FIRES

Maximum 3 coins analyzed simultaneously
Each coin runs through the full LangGraph pipeline
Results cached in Redis for dashboard
```

---

## 📋 Complete Crypto Signal Journey — Step by Step

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1  ──► Fetch candle data from Redis or Binance        │
│  STEP 2  ──► Calculate indicators (EMA · RSI · ADX · ATR)  │
│  STEP 3  ──► LangGraph agent starts                         │
│  STEP 4  ──► regime_node — detect market regime             │
│  STEP 5  ──► trend_node — check EMA direction + ADX         │
│  STEP 6  ──► risk_node — calculate SL/TP from swing levels  │
│  STEP 7  ──► grade_node — score ADX + RSI + Volume          │
│  STEP 8  ──► sizing_node — calculate position size          │
│  STEP 9  ──► finalize — build signal + write to Redis       │
│  STEP 10 ──► Save signal to SQLite database                 │
│  STEP 11 ──► Execute on Binance Futures                     │
│  STEP 12 ──► Send Telegram alert                            │
│  STEP 13 ──► Index signal into ChromaDB                     │
│  STEP 14 ──► LangSmith records full trace                   │
│  STEP 15 ──► Dashboard updates via WebSocket                │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 1–2 — Data Fetching and Indicators

```
For each coin:
    │
    ├── Check Redis first (fast — no API call)
    │   ├── HIT  ──► Use cached candles
    │   └── MISS ──► Fetch from Binance API
    │
    └── Calculate indicators on multiple timeframes
        1D · 4H · 1H

Indicators calculated:
    EMA 20 · EMA 50 · EMA 200
    RSI 14
    ADX 14
    ATR 14
    Volume MA 20
    Swing highs and lows
```

---

## Step 3 — LangGraph Agent Starts

```
The signal pipeline runs as a LangGraph
stateful agent graph.

Each step is a node.
State flows between nodes.
Every decision is logged.
Observable in LangSmith.

Initial state:
    coin        = "ETH"
    balance     = 1000.0
    df_4h       = dataframe
    df_1h       = dataframe
    signal      = True       ← starts as True
    reason      = ""         ← filled if rejected
    trace_steps = []         ← filled as nodes run
```

---

## Step 4 — regime_node

```
What it checks:
    ATR as percentage of price
    ADX value

Decision logic:
    ATR% > 4.0%  → VOLATILE  → REJECT
    ADX >= 25    → TRENDING  → size_mult = 1.0
    ADX >= 20    → RANGING   → size_mult = 0.7
    ADX < 20     → CHOPPY    → size_mult = 0.5

Why this matters:
    Volatile markets = unpredictable SL hits
    Choppy markets = false signals
    Only trending and ranging get full size

LangSmith records:
    Node: regime
    Label: trending / ranging / choppy / volatile
    ADX: current value
    ATR%: current value
    Size multiplier assigned
```

---

## Step 5 — trend_node

```
What it checks:
    Price vs EMA 200 → overall direction
    EMA 20 vs EMA 50 → trend confirmation
    ADX vs minimum threshold

Decision logic:
    Price > EMA200 AND EMA20 > EMA50 → LONG
    Price < EMA200 AND EMA20 < EMA50 → SHORT
    Anything else                    → NEUTRAL → REJECT

ADX check:
    Each coin has its own minimum ADX in config
    Default minimum is 18
    Below minimum → REJECT "adx_too_low"

Why EMA alignment matters:
    Price above EMA200 = long term bullish
    EMA20 above EMA50 = short term confirming
    Both must agree for a valid direction
    One without the other = mixed signal

LangSmith records:
    Node: trend
    Direction: LONG / SHORT / NEUTRAL
    ADX: value
    Rejection reason if applicable
```

---

## Step 6 — risk_node

```
What it checks:
    Swing high and swing low from recent candles
    ATR for buffer calculation
    Risk/reward ratio

SL placement:
    LONG  → SL below swing low  - (ATR × 0.5)
    SHORT → SL above swing high + (ATR × 0.5)

Validation:
    SL must be on correct side of entry
    SL% must be between 0.3% and 5.0%
    Too tight → REJECT "sl_too_tight"
    Too wide  → REJECT "sl_too_wide"

TP calculation:
    TP1 = entry ± (SL distance × 2.5)
    TP2 = entry ± (SL distance × 4.0)

RR check:
    Minimum RR = 1.5
    Below minimum → REJECT "rr_too_low"

LangSmith records:
    Node: risk
    Entry · SL · TP1 · SL% · RR
    Rejection reason if applicable
```

---

## Step 7 — grade_node

```
What it scores:
    Three factors → total out of 100

ADX score (max 40 points):
    ADX >= 30 → 40 pts  (strong trend)
    ADX >= 25 → 30 pts  (good trend)
    ADX >= 20 → 20 pts  (moderate trend)
    ADX < 20  →  0 pts  (weak)

RSI score (max 30 points):
    For LONG:
        RSI 40–45 → 30 pts  (oversold recovery)
        RSI 45–50 → 20 pts  (neutral momentum)
        RSI 50–65 → 10 pts  (mild momentum)
        Outside   →  0 pts

    For SHORT:
        RSI 55–60 → 30 pts  (overbought pullback)
        RSI 50–55 → 20 pts  (neutral momentum)
        RSI 35–50 → 10 pts  (mild momentum)
        Outside   →  0 pts

Volume score (max 30 points):
    Vol ratio >= 2.0 → 30 pts  (strong expansion)
    Vol ratio >= 1.5 → 20 pts  (good expansion)
    Vol ratio >= 1.0 → 10 pts  (average)
    Below 1.0        →  0 pts

Grade assignment:
    80–100 → A+  (auto-execute)
    65–79  → A   (auto-execute)
    50–64  → B   (REMOVED from trading)
    0–49   → F   (hard blocked)

Why B grade was removed:
    Live trading showed 13% win rate on B grades
    15 trades · -$122 PnL
    Data-driven decision to remove them
    Only A+ and A grades execute now

LangSmith records:
    Node: grade
    Score: total out of 100
    Grade: A+ / A / B / F
    ADX pts · RSI pts · Volume pts
```

---

## Step 8 — sizing_node

```
What it calculates:
    Dynamic position size based on
    multiple risk factors

Base risk:
    Paper mode → 1.5% of balance per trade
    Live mode  → 1.0% of balance per trade

Multipliers applied:
    Grade multiplier:
        A+ → 1.3x
        A  → 1.0x

    Regime multiplier:
        Trending → 1.0x
        Ranging  → 0.7x
        Choppy   → 0.5x

    Session multiplier:
        London/NY Overlap → 1.0x
        London or NY      → 1.0x
        Asia              → 0.5x
        Off Hours         → 0.0x (no trades)

    Correlation multiplier:
        Crypto coins are correlated
        Position size adjusted for portfolio
        to avoid overexposure

    Performance multiplier:
        Win rate above 60% → 1.2x
        Win rate below 40% → 0.7x
        Loss streak of 2+  → 0.9x

Safety checks:
    Daily loss limit → stop trading if hit
    Max open trades  → 2 at a time
    Max same direction → 1 at a time
    Session filter per coin config

Leverage calculation:
    Based on SL distance
    Tighter SL → higher leverage
    Wider SL   → lower leverage
    Maximum 10x

LangSmith records:
    Node: sizing
    Stake · Leverage · Risk% · Risk$
    All multipliers applied
    Rejection reason if applicable
```

---

## Step 9–15 — After Signal Confirmed

```
Step 9: finalize_node
    Build complete signal dictionary
    Write to Redis with 30 min TTL
    Include full trace of all node decisions

Step 10: Save to SQLite
    Only A+ and A grades saved
    Minimum RR of 2.0 required
    Duplicate check before saving

Step 11: Execute on Binance
    Set isolated margin mode
    Set leverage
    Place LIMIT order at entry price
    Monitor for fill (up to 4 hours)
    On fill → place SL and TP as algo orders

Step 12: Telegram alert
    Signal details sent immediately
    Entry · SL · TP · Grade · Score
    Mode indicator (LIVE or PAPER)

Step 13: Index to ChromaDB
    Signal chunk added to vector store
    Available for RAG queries immediately

Step 14: LangSmith traces everything
    Full agent execution recorded
    Every node timing logged
    Visible at smith.langchain.com

Step 15: Dashboard WebSocket push
    All connected clients updated
    Signal appears in radar immediately
```

---

## 🇮🇳 Indian Market — Complete ORB Journey

```
The Indian market engine runs completely
separately from the crypto engine.
Same infrastructure. Different logic entirely.
```

### Daily Schedule

```
03:00 UTC (8:30 IST)   → Fetch previous day range
03:30 UTC (9:00 IST)   → AngelOne session refresh
04:05 UTC (9:35 IST)   → ORB setup (lock opening range)
05:32 UTC (11:02 IST)  → Fetch pre-session range
Every 5 min (11–12 IST)→ Scan for breakdown
09:45 UTC (3:15 IST)   → Force close + daily summary
```

### Step by Step

```
STEP 1 — Session Login (3:30 IST)
    Login to AngelOne with TOTP
    Session valid for 24 hours
    Stored in Redis for persistence

STEP 2 — Previous Day Range (8:30 IST)
    Fetch yesterday's BANKNIFTY/FINNIFTY data
    Calculate high - low = prev_range
    Store in Redis

STEP 3 — ORB Setup (9:35 IST)
    Fetch first 15-minute candle (9:15–9:30)
    ORB High = candle high
    ORB Low  = candle low
    ORB Size = High - Low

    Validation:
        200 pts <= ORB size <= 350 pts → valid
        ORB too tight → skip today
        ORB too wide  → skip today

    Telegram alert with ORB levels

STEP 4 — Pre-Session Range (11:02 IST)
    Fetch 9:15–10:45 candles
    Calculate range = high - low
    Store as pre_range

STEP 5 — Entry Scan (11:00–12:00 IST)
    Every 5 minutes check:

    Volatility filter:
        pre_range >= 300 pts
        OR prev_range >= 600 pts
        If neither → skip today

    Week filter:
        Week 3 of month = expiry week → skip

    Breakdown check:
        Current price < ORB Low - 10 pts → SHORT signal

    If all pass → fire signal

STEP 6 — Signal Execution
    Entry = current price
    SL    = entry + (ORB size × 0.3)
    TP1   = entry - (ORB size × 1.0)
    TP2   = entry - (ORB size × 1.5)

    Example with ORB size = 250 pts:
        Entry = 45000
        SL    = 45000 + 75  = 45075
        TP1   = 45000 - 250 = 44750
        TP2   = 45000 - 375 = 44625

    Telegram alert with full details

STEP 7 — Outcome Tracking (every 5 min)
    Fetch live LTP from AngelOne
    Check if SL or TP hit
    Time exit at 2:30 PM IST regardless

    Outcomes:
        win     → TP1 hit
        loss    → SL hit
        timeout → 2:30 PM exit (can be positive or negative)

STEP 8 — End of Day Summary (3:15 IST)
    Telegram summary with:
        Signal outcome
        Points gained or lost
        Rupee value (30 rupees per point per lot)
        Month-to-date total
```

---

## 🤖 RAG Intelligence Layer — How It Works

```
User types: "why do my shorts fail?"
                    │
                    ▼
Intent detection
    → contains "short" and "fail"
    → search trades + signals collections
                    │
                    ▼
Question embedded as vector
using sentence-transformers locally
                    │
                    ▼
ChromaDB searched across collections
Finds most similar chunks by meaning
Not keyword matching — semantic search
                    │
                    ▼
Top 6 chunks retrieved:
    Trade #12: SHORT, loss, BTC bullish
    Trade #19: SHORT, loss, Asia session
    Signal #8: SHORT, grade A, loss
    Coin perf: SHORT trades 31% WR
                    │
                    ▼
Context sent to Groq with question
                    │
                    ▼
Answer returned with sources:
    "Your SHORT trades show 31% WR..."
    Sources: [trades, signals, coins]

LangSmith traces this entire flow
```

### The 5 Chunk Types

```
Type 1 — Trade Chunks
    One chunk per closed trade
    Contains: coin, direction, grade, session,
    regime, entry, exit, outcome, PnL, duration

Type 2 — Signal Chunks
    One chunk per closed signal
    Contains: score, factors, sweep score,
    BTC score, market score, outcome

Type 3 — Daily Summary Chunks
    One chunk per trading day
    Contains: total trades, win rate,
    sessions, regimes, coins, best/worst

Type 4 — Coin Performance Chunks
    One chunk per coin — updated on reindex
    Contains: win rate by session,
    win rate by regime, total PnL

Type 5 — Documentation Chunks
    README and WORKING.md split into
    500-word chunks with 50-word overlap
    Good for concept questions
```

---

## 📊 What Changed From Earlier Versions

```
Signal Pipeline:
    Before: Complex 16-factor scoring
            High complexity, low signal quality
            B grades losing money in live trading

    After:  Simple ADX + RSI + Volume scoring
            Data-driven simplification
            B grades removed after live results
            Grade A showing 50% win rate

Key lesson:
    Simple working system > complex broken system
    Live data beats theoretical models
    Iterate based on real results
```

---

## 🔒 Binance Order Execution — Full Detail

```
Entry order type: LIMIT
    Placed at signal entry price
    Waits up to 4 hours for fill
    If not filled → cancelled automatically

On fill:
    SL placed as STOP_MARKET algo order
    TP placed as TAKE_PROFIT_MARKET algo order
    Both use MARK_PRICE as trigger
    Both set to close full position

Monitoring:
    WebSocket streams watch for order fills
    On SL or TP hit → trade closed automatically
    PnL calculated including commission and funding
    Binance income API synced for accurate records

Slippage tracking:
    Entry slippage = fill price vs limit price
    Exit slippage  = fill price vs SL/TP price
    Both recorded per trade for analysis

Commission tracking:
    Entry commission recorded from order trades
    Exit commission recorded from order trades
    Funding fees fetched from income API
    Net PnL = realized PnL - commission - funding
```

---

## 📈 Portfolio Risk Management

```
Circuit breakers at multiple levels:

Daily loss limit:
    If today PnL < 2% of balance → stop trading

Max open trades:
    Maximum 2 trades at same time

Max same direction:
    Maximum 1 LONG and 1 SHORT at same time

Coin cooldown:
    After SL hit → coin paused for 4 hours

Portfolio drawdown levels:
    Level 1 (5% DD)  → size reduced to 70%
    Level 2 (10% DD) → size reduced to 40%
    Level 3 (15% DD) → size reduced to 20%
    Level 4 (20% DD) → trading halted
    Level 5 (30% DD) → trading halted

Session filter:
    Off Hours → no new trades
    Asia session → 50% size only
```

---

## 🔄 Complete Journey Summary

| Step | What Happens | Market |
|------|-------------|--------|
| 1–2 | Fetch data + calculate indicators | Crypto |
| 3 | LangGraph agent starts | Crypto |
| 4 | regime_node — volatile check | Crypto |
| 5 | trend_node — EMA + ADX check | Crypto |
| 6 | risk_node — SL/TP calculation | Crypto |
| 7 | grade_node — ADX+RSI+Volume score | Crypto |
| 8 | sizing_node — dynamic position size | Crypto |
| 9 | finalize — build + write to Redis | Crypto |
| 10–12 | Save + execute + alert | Crypto |
| 13–15 | Index + trace + dashboard | Crypto |
| A | Session login + ORB setup | Indian |
| B | Volatility + week validation | Indian |
| C | Breakdown detection 11am–12pm | Indian |
| D | Signal execution + tracking | Indian |
| E | Time exit + daily summary | Indian |

---

<div align="center">

```
Signal Engine v5 is not a theoretical system.

It runs live on AWS every 15 minutes.
It has executed real trades on Binance Futures.
It has real win rates and real PnL data.
It removed B grades because live data said so.
It tracks Indian markets with a separate strategy.
Every AI operation is observable in LangSmith.
Every trade question is answerable via RAG.

Simple. Working. Iterating.
That is the edge.
```

[![Live System](https://img.shields.io/badge/🔴_See_It_Live-signal--engine--v5.vishalkool.top-00ff88?style=for-the-badge)](https://signal-engine-v5.vishalkool.top)

**Vishal Katike** · vishalkool166@gmail.com · +91 8978439995 · Hyderabad, India

</div>