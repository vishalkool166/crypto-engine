# How A Signal Is Born — Complete Journey

<div align="center">

*A step-by-step technical deep dive into how Signal Engine v5 thinks, decides, and acts.*

[![Live System](https://img.shields.io/badge/🔴_LIVE-Running_24%2F7-00ff88?style=for-the-badge)](https://signal-engine-v5.vishalkool.top)

</div>

---

## 🧠 The Big Picture

```
┌─────────────────────────────────────────────────────────────┐
│                    SIGNAL ENGINE v5                          │
│                                                              │
│   "Not a bot that buys when RSI is low.                     │
│    Every signal has a reason — a story."                    │
│                                                              │
│  ┌──────────────┐         ┌──────────────────────────────┐  │
│  │   BINANCE    │◄───────►│      SIGNAL ENGINE           │  │
│  │   FUTURES    │  CCXT   │      (The Brain)             │  │
│  │   API        │         │      Watches · Scores ·      │  │
│  └──────────────┘         │      Decides · Executes      │  │
│                           └──────────────────────────────┘  │
│                                        │                     │
│                                        ▼                     │
│                           ┌──────────────────────────────┐  │
│                           │         REDIS                │  │
│                           │    (The Nervous System)      │  │
│                           │    Real-time data layer      │  │
│                           └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

Signal Engine is the **brain** — it watches the market, scores every coin,
decides what is worth trading, and executes directly on Binance via CCXT.

Redis is the **nervous system** — real-time market data flows through it.
Signal Engine reads from Redis first, falls back to Binance API if needed.

---

## ⏱️ The Scan Cycle

```
UTC Clock
    │
    ├── :00 ──► SCAN FIRES
    ├── :15 ──► SCAN FIRES
    ├── :30 ──► SCAN FIRES
    └── :45 ──► SCAN FIRES

Maximum 3 coins analyzed simultaneously
(respects Binance API rate limits)
```

Every 15 minutes, Signal Engine wakes up and checks every coin
in the active universe — controlled via the dashboard.

---

## 📋 Complete Signal Journey — 23 Steps

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1 ──► Fetch Market Data                               │
│  STEP 2 ──► Clean + Validate Data                           │
│  STEP 3 ──► Calculate Indicators                            │
│  STEP 4 ──► Run 4 ICT Engine Checks                         │
│  STEP 5 ──► Detect Market Regime                            │
│  STEP 6 ──► No-Trade Engine (Bouncer)                       │
│  STEP 7 ──► Score 16 Confluence Factors                     │
│  STEP 8 ──► Calculate Final Score                           │
│  STEP 9 ──► Grade Signal (A+/A/B/C/F)                       │
│  STEP 10 ──► Grade B Quality Filter                         │
│  STEP 11 ──► Direction Decision (LONG/SHORT)                │
│  STEP 12 ──► 15M Entry Refinement                           │
│  STEP 13 ──► Structure-Aware SL Calculation                 │
│  STEP 14 ──► TP Calculation                                 │
│  STEP 15 ──► Risk Sizing + Capital Allocation               │
│  STEP 16 ──► ML Gate Check                                  │
│  STEP 17 ──► Write Signal to Redis                          │
│  STEP 18 ──► Content Pipeline Triggered                     │
│  STEP 19 ──► Execute on Binance Futures                     │
│  STEP 20 ──► Telegram Alert Sent                            │
│  STEP 21 ──► Outcome Sync (every 30 min)                    │
│  STEP 22 ──► ML Training (after 100 trades)                 │
│  STEP 23 ──► Commentary Posts (no-signal scans)             │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 1 — Fetching Market Data

```
For each coin:
    │
    ├── Check Redis first (fast, no API call)
    │   ├── HIT  ──► Use cached data ✅
    │   └── MISS ──► Fall back to Binance API
    │
    └── Always fetch from external:
        ├── Fear & Greed Index ──► alternative.me
        └── News Filter ──────► Finnhub economic calendar
```

### Redis Data Keys

| Data | Redis Key | TTL |
|------|-----------|-----|
| OHLCV candles | `candles:{coin}USDT:{tf}` | 900s |
| Current price | `ticker:{coin}USDT` | 60s |
| Funding rate | `funding:{coin}USDT` | 300s |
| Open interest | `oi:{coin}USDT` | 300s |
| OI change % | `oi_change:{coin}USDT` | 300s |
| Long/short ratio | `ls_ratio:{coin}USDT` | 300s |

### Candle Coverage

| Timeframe | Candles | Covers |
|-----------|---------|--------|
| Weekly (1W) | 500 | ~10 years |
| Daily (1D) | 1000 | ~3 years |
| 4 Hour (4H) | 500 | ~83 days |
| 1 Hour (1H) | 300 | ~12 days |
| 15 Minute (15M) | 200 | ~2 days |

> All candles saved to SQLite. Next scan loads from SQLite
> and only fetches new candles incrementally.

---

## Step 2 — Data Cleaning

```
Raw candle data
      │
      ▼
┌─────────────────────────────────────┐
│         VALIDATION CHECKS           │
│                                     │
│  ✓ Missing candles (gaps)           │
│  ✓ Duplicate timestamps             │
│  ✓ High < Low (impossible data)     │
│  ✓ Zero prices (exchange glitch)    │
│  ✓ Moves > 50% (data error)         │
└──────────────┬──────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
   CLEAN ✅        TOO DIRTY ❌
   Continue        Skip coin entirely
```

> *Better to miss a signal than trade on corrupted data.*

---

## Step 3 — Running The Indicators

Calculated on **all 4 timeframes** (1W · 1D · 4H · 1H):

```
┌─────────────────────────────────────────────────────────────┐
│                    INDICATOR SUITE                           │
├──────────────────────┬──────────────────────────────────────┤
│ EMA 20 / 50 / 200    │ Trend direction                      │
│ RSI (14)             │ Momentum strength                    │
│ MACD                 │ Buying/selling pressure              │
│ ATR (14)             │ Normal price movement range          │
│ ADX (14)             │ Trend strength vs noise              │
│ Bollinger Bands      │ Squeeze vs expansion                 │
│ Swing Highs/Lows     │ Where price reversed before          │
│ Volume Profile       │ Where most trading happened          │
│ CVD                  │ Buyers vs sellers in control         │
│ BOS / CHoCH          │ Structure break or character change  │
│ Order Blocks         │ Institutional order zones            │
│ Fair Value Gaps      │ Price imbalances to fill             │
└──────────────────────┴──────────────────────────────────────┘
```

---

## Step 4 — The Four ICT Engine Checks

These are the **core concepts** the system is built on.

### 💧 Engine 1 — Liquidity Sweep

```
Key price level (swing low / PDL / weekly low)
         │
         │  Big players push price DOWN
         │  to trigger everyone's stop losses
         ▼
    ┌─────────┐
    │  SWEEP  │  ← Price dips below level briefly
    └────┬────┘
         │  Immediately reverses UP
         │  Big players collected liquidity
         ▼
    Real move begins ──► Signal Engine detects this

Checks:
  ├── Did price dip below key level?
  ├── Did it immediately recover?
  ├── How strong was the move? (ATR multiple)
  ├── How much volume on that candle?
  └── How recent? (5 candles = high · 20 candles = expired)

Score: 0 to 12
```

### ⚡ Engine 2 — Displacement

```
After sweep ──► Institutions push price HARD in real direction

Think of it like a slingshot:
  Sweep ──► pulls rubber band back (fake move)
  Displacement ──► lets go (real move)

Checks:
  ├── Candle bigger than 1.5x normal daily range?
  ├── Body takes up more than 60% of candle range?
  ├── Price closed beyond previous candle high?
  └── Volume higher than normal?

Score: 0 to 11
```

### 🎯 Engine 3 — Retest

```
After displacement ──► Price returns to launch zone

Think of it like a rocket:
  Displacement ──► rocket blasts off
  Retest ──────► briefly dips back to launch pad
  Entry ────────► get on board here

Zone Priority:
  1st ──► Order Block (institutional orders)
  2nd ──► Fair Value Gap (price imbalance)
  3rd ──► EMA 20 or 50 (dynamic support)

Checks:
  ├── Valid zone exists?
  ├── Price currently inside zone?
  ├── Rejection candle shown?
  └── Volume absorbed in zone?

Score: 0 to 12
```

### 📦 Engine 4 — Order Blocks

```
Before big move ──► Institutions place massive orders
Last candle before move ──► The Order Block
                            (footprint of big money)

When price returns ──► Institutions defend their zone
That defense ──────► Creates the bounce

Checks:
  ├── Last bearish candle before bullish move (bull OB)
  ├── Last bullish candle before bearish move (bear OB)
  ├── Price in zone or approaching?
  ├── Touch count (each touch weakens it)
  └── Zone mitigated? (broken = invalid)

Score: 0 to 10
```

---

## Step 5 — Market Regime Detection

```
┌─────────────────────────────────────────────────────────────┐
│                   REGIME CLASSIFIER                          │
├──────────────────────┬──────────────┬───────────────────────┤
│ Regime               │ Condition    │ Tradeable?            │
├──────────────────────┼──────────────┼───────────────────────┤
│ 📈 Trending Bullish  │ ADX > 25 ↑  │ ✅ Yes                │
│ 📉 Trending Bearish  │ ADX > 25 ↓  │ ✅ Yes                │
│ 💥 Volatility Expand │ BB wide+vol  │ ✅ Yes                │
│ 〰️ Weak Trend        │ ADX 18-25   │ ⚠️ Reduced            │
│ ➡️ Ranging           │ BB narrow    │ ❌ No                 │
│ 🌀 Choppy            │ ADX < 18    │ 🚫 Hard blocked       │
└──────────────────────┴──────────────┴───────────────────────┘

Think of regime like weather.
You only go sailing in good weather.
Choppy market = stay home.
```

---

## Step 6 — The No-Trade Engine (Bouncer)

```
Signal approaching ──► BOUNCER checks conditions
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
        HARD BLOCKS                     SOFT BLOCKS
        (Kill signal)                   (Reduce score)
              │                               │
┌─────────────┴──────────────┐  ┌────────────┴────────────────┐
│ ✗ Market choppy            │  │ -6 RSI deeply overbought    │
│ ✗ Weekly/daily conflict    │  │ -4 No liquidity sweep       │
│ ✗ Funding > 0.08%          │  │ -3 News approaching 1hr     │
│ ✗ High-impact news active  │  │ -3 No retest zone active    │
│ ✗ Retest zone failed       │  │ -3 Crowded positioning 68%+ │
│ ✗ BTC unstable (2+ warns)  │  │ -3 4H conflicts daily       │
│ ✗ No sweep AND no disp     │  └─────────────────────────────┘
│ ✗ Asia / Off Hours session │
└────────────────────────────┘
```

---

## Step 7-8 — Scoring + Final Score

```
16 FACTORS SCORED
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│  Total Earned Points / 114 (max possible) × 100             │
│                    =                                         │
│              CONFLUENCE SCORE (0-100)                        │
│                                                              │
│  Then subtract soft block penalties                          │
│                    =                                         │
│                FINAL SCORE                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 9 — Signal Grading

```
Final Score
    │
    ├── 85-100 ──► 🏆 A+  Auto-execute · 2% risk · 2.5x TP
    ├── 68-84  ──► ✅ A   Auto-execute · 1.5% risk · 2.0x TP
    ├── 52-67  ──► 👀 B   Paper only + quality filter · 1% risk
    ├── 38-51  ──► ⏳ C   Watch only · Never trade
    └── 0-37   ──► 🚫 F   Hard blocked · Never trade
```

---

## Step 10 — Grade B Quality Filter

```
Grade B signal
      │
      ▼
ALL of these must pass:
  ├── ✅ Paper mode active (never in live)
  ├── ✅ Market score ≥ 65
  ├── ✅ Session = London / NY / London+NY Overlap
  ├── ✅ BTC score ≥ 4 (not conflicting)
  └── ✅ Maximum 1 hard block present
      │
      ├── ALL PASS ──► Execute in paper mode
      └── ANY FAIL ──► Mark SKIP · Save to DB for ML analysis
```

> *B grades collect training data for ML without real risk.*
> *ML learns which B grades actually win.*

---

## Step 11 — Direction Decision

```
1D Trend + 4H Trend
      │
      ├── Both BULLISH ──► LONG ✅
      ├── Both BEARISH ──► SHORT ✅
      └── CONFLICT ──────► Downgrade to C · No trade ❌
```

---

## Step 12 — 15 Minute Entry Refinement

```
4H signal confirmed
      │
      ▼
Zoom into 15M chart
      │
      ├── Look for entry patterns:
      │   ├── Bullish engulfing
      │   ├── Hammer / Pin bar
      │   ├── Shooting star
      │   ├── Bearish engulfing
      │   └── Micro sweep (15M stop hunt)
      │
      ├── Also check:
      │   ├── Price above EMA20 (for longs)
      │   ├── Volume above average
      │   └── Micro sweep present
      │
      ├── 15M CONFIRMS ──► Use 15M price as entry ✅
      └── 15M NO CONFIRM ──► Use 4H price · -2 score penalty
```

---

## Step 13 — Structure-Aware SL

```
SL placed at ACTUAL trade invalidation point
(not a random ATR multiple)

Priority:
  1st ──► Below retest zone bottom + ATR×0.15 buffer
  2nd ──► Below sweep low + ATR×0.1 buffer
  3rd ──► Beyond swing point + ATR×0.1 buffer
  4th ──► ATR × regime multiplier (fallback only)

ATR Multipliers by Regime:
  Expansion  ──► 2.5x
  Trending   ──► 2.0x
  Weak Trend ──► 1.5x
```

---

## Step 14 — TP Calculation

```
Single TP only (no TP1/TP2 split)
Cleaner ML labels = full win or full loss

Structure levels checked:
  ├── Swing highs/lows
  ├── Previous day high/low
  ├── Previous week high/low
  └── Volume Area High/Low

Grade multipliers (minimum distance):
  A+ ──► 2.5x risk distance
  A  ──► 2.0x risk distance
  B  ──► 1.5x risk distance

Rule: Use nearest structure OR grade minimum
      whichever gives better reward
```

---

## Step 15 — Risk Sizing

```
Risk Amount  = Capital × Grade Risk %
Position     = Risk Amount ÷ SL Distance %
Margin Used  = Position ÷ Leverage

Grade Risk %:
  A+ ──► 2.0% of capital
  A  ──► 1.5% of capital
  B  ──► 1.0% of capital

Dynamic leverage based on:
  ├── ATR% (volatility)
  ├── ADX (trend strength)
  └── Drawdown (performance history)
```

---

## Step 16 — ML Gate Check

```
Signal ready
      │
      ▼
Is ML enabled? (100+ closed trades exist)
      │
      ├── NO ──► All A+/A/B signals pass through
      │
      └── YES ──► Feed 16 factor scores to LightGBM
                        │
                        ▼
              Win Probability (0.0 - 1.0)
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
          ≥ 0.65               < 0.65
          PASS ✅              BLOCK ❌
          Continue             Signal filtered
```

---

## Step 17 — Signal Written to Redis

```json
{
  "symbol": "AVAXUSDT",
  "side": "short",
  "entry": 6.32,
  "stoploss": 6.80,
  "tp1": 5.90,
  "grade": "A",
  "score": 71,
  "valid_until": 1782034000,
  "signal_id": 47,
  "regime": "TRENDING BEARISH",
  "session": "London/NY Overlap",
  "ml_probability": 0.73,
  "tp_mult": 2.0,
  "actual_rr": 1.9
}
```

```
Key: signal:{coin}USDT
TTL: 900 seconds (15 minutes)
```

---

## Step 18 — Content Pipeline

```
A+/A Signal Generated
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  CHART GENERATED (mplfinance)                          │
│  ├── 4H candlestick · last 50 candles                 │
│  ├── Entry · SL · TP lines drawn                      │
│  ├── Sweep zone shaded yellow                         │
│  ├── Grade badge + score watermark                    │
│  └── Saved as PNG 1200×675px                          │
└──────────────────────┬─────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────┐
│  GROQ LLM WRITES POST (llama-3.3-70b)                 │
│  ├── Under 280 characters                             │
│  ├── Tone rotation:                                   │
│  │   ├── 70% professional                            │
│  │   ├── 20% educational                             │
│  │   └── 10% humor                                   │
│  └── Includes: coin · direction · entry · thesis      │
└──────────────────────┬─────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────┐
│  TELEGRAM APPROVAL                                     │
│                                                        │
│  📊 Chart image sent                                  │
│  📝 Draft post sent (char count shown)                │
│                                                        │
│  [✅ Approve & Post]  [❌ Discard]                    │
│  [✏️ Edit Draft]      [🔄 Regenerate]                 │
└────────────────────────────────────────────────────────┘
```

---

## Step 19 — Binance Execution

```
Signal in Redis
      │
      ▼
Signal Engine reads signal
      │
      ▼
Final checks:
  ├── Signal still valid (not expired)
  ├── Entry price within 0.5% of current price
  ├── Grade is A+, A, or B
  └── No existing position for this coin
      │
      ├── ALL PASS ──► Place MARKET order via CCXT
      │                     │
      │                     ▼
      │               Order FILLED
      │                     │
      │                     ▼
      │               Place SL (STOP_MARKET)
      │               Place TP (TAKE_PROFIT_MARKET)
      │
      └── ANY FAIL ──► Trade rejected · Log reason

Exit conditions:
  ├── Price hits TP ──► tp_hit
  ├── Price hits SL ──► sl_hit
  └── Manual close ──► manual_close
```

---

## Step 20 — Telegram Alert

```
🏆 Grade A+ — SHORT
━━━━━━━━━━━━━━━━━━━━━━

AVAXUSDT — 📉 SHORT
Confidence: High (87/100)
ML Prob: ✅ 73.2%
Regime: TRENDING BEARISH
Session: London/NY Overlap
Time: 06:45 PM IST

━━━━━━━━━━━━━━━━━━━━━━
Entry:   $6.3200
SL:      $6.8000 (7.59%)
TP:      $5.9000 (2.5x risk)
R:R:     1:1.9

━━━━━━━━━━━━━━━━━━━━━━
Risk:    $20.00
Size:    $263.00

Why This Trade:
✔ Liquidity swept at Weekly High — 2 candles ago
✔ Strong bearish displacement — 2.3x ATR, vol 1.9x
✔ BTC bearish — confirms direction
⚠ OI exhaustion — momentum may be fading

[📊 Factors]  [⚠️ Risks]
```

---

## Step 21 — Outcome Sync

```
Every 30 minutes:
      │
      ▼
Read all closed trades from Binance
      │
      ▼
Match to Signal table by:
  ├── Same coin
  ├── Same direction
  ├── Entry price within 2% tolerance
  └── Closest timestamp match
      │
      ▼
Update Signal record:
  ├── outcome = "win" or "loss"
  ├── pnl = actual PnL
  └── exit_price = actual exit

This feeds the ML training pipeline.
Without sync ──► ML has no labels to learn from.
```

---

## Step 22 — ML Training

```
Hourly check:
      │
      ▼
100+ closed trades with factor scores?
      │
      ├── NO ──► Wait · Keep collecting
      │
      └── YES ──► Train LightGBM
                        │
                        ▼
            Feature Matrix:
            ├── All 16 factor scores
            ├── sweep/retest/disp scores
            ├── btc_score · market_score
            ├── grade · regime · session
            ├── direction · funding
            └── slippage · commission

            Label: win=1 · loss=0

            Training:
            ├── 200 estimators
            ├── 5-fold cross validation
            ├── Balanced class weights
            └── Model saved to ml/models/

            After training:
            ├── ML_ENABLED = True
            ├── All signals run through predictor
            ├── Telegram notification sent
            └── Auto-retrains every 50 new trades
```

---

## Step 23 — Commentary Posts

```
Scan completes with NO tradeable signals
      │
      ▼
Is market interesting enough to post about?
      │
      ├── Fear/Greed < 20 (extreme fear)
      ├── Fear/Greed > 80 (extreme greed)
      ├── 70%+ coins in choppy regime
      ├── Average funding > 0.06%
      └── Weekend market
      │
      ├── YES ──► Groq writes commentary
      │           Tone: 40% humor · 30% educational
      │           Sent to Telegram for approval
      │
      └── NO ──► Silent scan · No post

Cooldown by session:
  London/NY Overlap ──► 1 hour
  London or NY ──────► 2 hours
  Asia ──────────────► 6 hours
  Weekend ───────────► 8 hours

Example posts:
  "Market regime: choppy. ADX: 12.
   Translation: nobody knows anything. #Crypto"

  "Funding at 0.09%. Someone is very confident.
   History suggests otherwise. #Bitcoin"
```

---

## 📊 Complete Journey Summary

| Step | What Happens | Output |
|------|-------------|--------|
| 1 | Fetch market data | OHLCV + funding + OI |
| 2 | Clean + validate | Clean candle data |
| 3 | Calculate indicators | EMA · RSI · MACD · ATR · ADX |
| 4 | 4 ICT engine checks | Sweep · Disp · Retest · OB scores |
| 5 | Detect regime | Trending / Ranging / Choppy |
| 6 | No-trade bouncer | Hard blocks · Soft penalties |
| 7 | Score 16 factors | Individual factor scores |
| 8 | Calculate final score | 0-100 confluence score |
| 9 | Grade signal | A+ / A / B / C / F |
| 10 | B grade filter | Pass or SKIP |
| 11 | Direction decision | LONG / SHORT / No trade |
| 12 | 15M entry refinement | Exact entry price |
| 13 | SL calculation | Structure-aware stop loss |
| 14 | TP calculation | Nearest structure target |
| 15 | Risk sizing | Position size + leverage |
| 16 | ML gate | Win probability check |
| 17 | Write to Redis | Signal payload TTL 900s |
| 18 | Content pipeline | Chart + Groq draft + Telegram |
| 19 | Execute on Binance | Market order + SL + TP |
| 20 | Telegram alert | Full signal details |
| 21 | Outcome sync | Win/loss label for ML |
| 22 | ML training | LightGBM model update |
| 23 | Commentary posts | Market insight tweets |

---

<div align="center">

```
Signal Engine is not a bot that buys when RSI is low
and sells when RSI is high.

Every signal has a reason — a story.

Sweep happened here.
Institutions displaced price there.
Retest gave entry here.
Structure says direction is this way.
BTC agrees. Volume confirms.
ML says 73% probability.

When enough of those pieces align at the same time
— that is the signal.
That is the edge.
Not any single indicator.
The alignment of all of them together.

The ML layer learns which specific combinations
actually produce winning trades in real conditions.
Over time the system gets smarter about its own signals.
```

[![Live System](https://img.shields.io/badge/🔴_See_It_Live-signal--engine--v5.vishalkool.top-00ff88?style=for-the-badge)](https://signal-engine-v5.vishalkool.top)

</div>