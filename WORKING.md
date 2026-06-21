# How A Signal Is Born — Complete Journey

## The Big Picture First

Signal Engine is split into two parts that work together.

**Signal Engine** is the brain.
It watches the market, scores every coin, decides what is worth trading,
and writes the decision to a shared memory called Redis.

**Freqtrade** is the body.
It reads from Redis, places real or simulated orders on Binance,
manages the trade until it closes, and reports the result back.

**Redis** is the nervous system connecting them.
Signal Engine writes. Freqtrade reads. No direct connection needed.

Think of it like a trading desk.
The analyst (Signal Engine) does the research and writes a trade idea on a whiteboard.
The trader (Freqtrade) reads the whiteboard and executes the order.
The whiteboard (Redis) is always up to date.

---

## The Scan Cycle — Every 15 Minutes

A scheduler fires at exactly :00, :15, :30, :45 UTC.

When it fires, Signal Engine wakes up and says:
"Time to check every coin in the universe."

It goes through all enabled coins — you control which coins are active
via the dashboard coin universe panel.

Maximum 3 coins analyzed at the same time to respect Binance API limits.

---

## Step 1 — Fetching Market Data

For each coin, Signal Engine first checks Redis.
Freqtrade has already pushed fresh market data there.

If Redis has it — use it directly. No Binance API call needed.
If Redis does not have it — fall back to Binance directly.

| Data | Redis Key | TTL |
|------|-----------|-----|
| OHLCV candles | candles:{coin}USDT:{tf} | 900s |
| Current price | ticker:{coin}USDT | 60s |
| Funding rate | funding:{coin}USDT | 300s |
| Open interest | oi:{coin}USDT | 300s |
| OI change % | oi_change:{coin}USDT | 300s |
| Long/short ratio | ls_ratio:{coin}USDT | 300s |

These two always hit external APIs directly:
- Fear and greed index → alternative.me
- News filter → Finnhub economic calendar

Candles downloaded per timeframe:
| Timeframe | Candles | Covers |
|-----------|---------|--------|
| Weekly (1W) | 500 | ~10 years |
| Daily (1D) | 1000 | ~3 years |
| 4 Hour (4H) | 500 | ~83 days |
| 1 Hour (1H) | 300 | ~12 days |
| 15 Minute (15M) | 200 | ~2 days |

All candles are also saved to SQLite for persistence.
Next scan loads from SQLite and only fetches new candles incrementally.

---

## Step 2 — Data Cleaning

Before doing anything with the data the app validates it.

| Check | What It Catches |
|-------|----------------|
| Missing candles | Gaps in history |
| Duplicate candles | Same timestamp twice |
| High lower than low | Impossible price data |
| Zero prices | Exchange glitch |
| Extreme moves over 50% | Data error not real move |

If data is too dirty the coin is skipped entirely.
Better to miss a signal than trade on corrupted data.

---

## Step 3 — Running The Indicators

The app calculates all technical indicators on the clean candle data.
This runs on all 4 timeframes — weekly, daily, 4H, 1H.

Think of indicators like different doctors examining the same patient.
Each one looks at a different thing and gives their opinion.

| Indicator | What It Tells Us |
|-----------|-----------------|
| EMA 20, 50, 200 | Is price above or below its average — trend direction |
| RSI | Is the move getting tired or still strong |
| MACD | Is buying or selling pressure growing |
| ATR | How much does price normally move per candle |
| ADX | Is there actually a trend or just noise |
| Bollinger Bands | Is price squeezed or expanding |
| Swing highs/lows | Where did price reverse before |
| Volume profile | Where did most trading happen |
| CVD | Are buyers or sellers actually in control |
| BOS/CHoCH | Did market structure break or change character |
| Order blocks | Where did institutions place large orders |
| Fair Value Gaps | Where did price move so fast it left a gap |

---

## Step 4 — The Four Engine Checks

Before scoring anything the app runs 4 specific checks.
These are the core ICT concepts the system is built on.

---

### Engine 1 — Liquidity Sweep Detection

**What is a liquidity sweep:**

Imagine everyone puts their stop losses just below a key price level.
Big players — banks, institutions, whales — they know where those stops are.
They push price down briefly to trigger all those stops,
collect all that liquidity, then reverse and go up hard.

That brief dip below the level is called a liquidity sweep.

**What the app checks:**
- Did price dip below a key level (previous day low, weekly low, swing low)
- Did it immediately come back above that level
- How strong was the move (ATR multiple)
- How much volume was on that candle
- How recent was it (last 5 candles = high relevance, 20 candles = expired)

**Score: 0 to 12**

---

### Engine 2 — Displacement Detection

**What is displacement:**

After the sweep happens, the big players have collected their liquidity.
Now they push price hard in the real direction.
This hard push is called displacement — a big strong candle that moves fast.

Think of it like a slingshot.
The sweep pulls the rubber band back (fake move down).
Displacement is when they let go (real move up).

**What the app checks:**
- Was there a candle bigger than 1.5x the normal daily range
- Did the candle body take up more than 60% of the candle range
- Did price close beyond the previous candle high
- Was volume higher than normal on that candle

**Score: 0 to 11**

---

### Engine 3 — Retest Detection

**What is a retest:**

After the big displacement candle, price often comes back to test
the zone where it launched from.
This is the entry opportunity.

Think of it like a rocket launch.
The rocket blasts off (displacement).
Before going to the moon it briefly dips back toward the launch pad (retest).
That brief dip back is where you want to get on board.

**What the app checks:**
- Is there a valid zone to retest — Order Block, Fair Value Gap, or EMA
- Is price currently inside that zone
- Did price show a rejection candle inside the zone
- Was volume absorbed inside the zone

**Zone priority:**
1. Order Block — where institutions placed big orders
2. Fair Value Gap — price moved so fast it left a gap
3. EMA 20 or 50 — dynamic support/resistance

**Score: 0 to 12**

---

### Engine 4 — Order Block Detection

**What is an order block:**

Before a big move, institutions place massive orders.
The last candle before the big move is called the order block.
It is like a footprint — evidence that big money was here.

When price comes back to that zone, institutions defend it
because they still have orders there.
That defense is what creates the bounce.

**What the app checks:**
- Last bearish candle before a big bullish move (bullish order block)
- Last bullish candle before a big bearish move (bearish order block)
- Is price currently in that zone or approaching it
- Has the zone been touched before (each touch weakens it)
- Has the zone been fully broken (mitigated — no longer valid)

**Score: 0 to 10**

---

## Step 5 — Market Regime Detection

Before scoring the signal the app asks one big question:
**Is this even a tradeable market right now?**

| Regime | What It Means | Tradeable |
|--------|--------------|-----------|
| Trending Bullish | Strong uptrend, ADX above 25 | Yes |
| Trending Bearish | Strong downtrend, ADX above 25 | Yes |
| Volatility Expansion | Big breakout happening | Yes |
| Weak Trend | ADX developing, 18-25 | Reduced confidence |
| Ranging | Flat, narrow Bollinger Bands | No |
| Choppy | ADX below 18 on both 1D and 4H | Hard blocked |

Think of regime like weather.
You only go sailing in good weather.
Choppy market means stay home.

---

## Step 6 — The No-Trade Engine

This is the bouncer at the door.
Even if everything looks good, certain conditions
immediately kill the signal before scoring even starts.

**Hard Blocks — Automatic rejection:**

| Block | Reason |
|-------|--------|
| Market is choppy | ADX too weak — no trend |
| Weekly and daily conflict | Big picture disagrees |
| Extreme funding rate above 0.08% | Squeeze risk too high |
| High impact news event active | Too unpredictable |
| Retest zone failed | Setup already invalidated |
| BTC unstable with 2+ warnings | Market too risky |
| No sweep AND no displacement | Minimum condition not met |
| Asian or Off Hours session | Low volume — fake moves |

**Soft Blocks — Reduce the score but do not kill it:**

| Penalty | Points Deducted |
|---------|----------------|
| RSI deeply overbought/oversold | -6 points |
| News event approaching in 1 hour | -3 points |
| No liquidity sweep detected | -4 points |
| No retest zone active | -3 points |
| Crowded positioning (68%+ longs or shorts) | -3 points |
| 4H structure conflicts daily | -3 points |

---

## Step 7 — Scoring All 16 Confluence Factors

Now the real scoring happens.
Think of this like a judge scoring an Olympic gymnast.
Each judge scores one aspect.
All scores added up give the final result.

The app has 16 judges — each looking at one specific thing.

**Why 16 factors?**
Because no single indicator is reliable alone.
When 12 out of 16 things align — that is a high probability setup.
When only 4 align — that is noise.

| Factor | Weight | Simple Explanation |
|--------|--------|-------------------|
| Liquidity Sweep | 12 | Did big players hunt stops before this move |
| Retest Confirmation | 12 | Is price giving a safe entry point right now |
| Displacement | 11 | Did institutions push price with conviction |
| Market Regime | 10 | Is this a market worth trading at all |
| Weekly Filter | 10 | Is the big picture supporting this direction |
| Market Structure | 9 | Is the market organized in our direction |
| Session Timing | 8 | Is there enough real participation right now |
| BTC Alignment | 8 | Is the market leader supporting this trade |
| OI Behavior | 7 | Is smart money actually entering |
| Volume Expansion | 7 | Is there real participation behind this move |
| Funding Rate | 6 | Is the market too crowded in one direction |
| RSI Divergence | 4 | Is momentum secretly building or fading |
| Order Blocks | 4 | Are we entering at an institutional level |
| ATR Volatility | 3 | Is volatility in a tradeable range |
| RSI Context | 2 | Is momentum in a healthy zone for entry |
| MACD Histogram | 1 | Is momentum mathematically confirmed |

---

## Step 8 — Calculating The Final Score

All 16 factor scores are added up.

```
Total earned points / Maximum possible points × 100 = Score out of 100
```

Maximum possible = 114 points across all 16 factors.

Then soft block penalties are subtracted.

```
Score after penalties = Final score
```

---

## Step 9 — Grading

| Score | Grade | Action | Mode |
|-------|-------|--------|------|
| 85-100 | A+ | Execute | Paper + Live |
| 68-84 | A | Execute | Paper + Live |
| 52-67 | B | Execute with filter | Paper only |
| 38-51 | C | Watch | Never |
| 0-37 | F | Hard blocked | Never |

---

## Step 10 — Grade B Quality Filter

If grade is B the app runs an additional check before allowing execution.

B grades are lower quality setups.
They are allowed in paper mode to collect training data for ML.
But not every B grade is worth trading — only the better ones.

**B grade passes if ALL of these are true:**
- Paper mode is active (never in live)
- Market score is at least 65 out of 100
- Session is London, NY, or London/NY Overlap
- BTC score is at least 4 (BTC not strongly conflicting)
- Maximum 1 hard block exists (session block is acceptable)

If B grade fails this filter it is marked SKIP and not forwarded to Freqtrade.
The signal is still saved to the database for analysis.

---

## Step 11 — Direction Decision

If grade passes the app decides direction:

| Condition | Direction |
|-----------|----------|
| 1D bullish AND 4H bullish | LONG |
| 1D bearish AND 4H bearish | SHORT |
| Conflict | No trade |

Both timeframes must agree.
If they disagree the signal is downgraded to C and not traded.

---

## Step 12 — 15 Minute Entry Refinement

Now the app zooms into the 15 minute chart
to find the exact best entry price.

It looks for a specific candle pattern:

| Pattern | Meaning |
|---------|---------|
| Bullish engulfing | Big green candle swallowed previous red candle |
| Hammer/Pin bar | Long wick below, closed high — rejection of lows |
| Shooting star | Long wick above, closed low — rejection of highs |
| Bearish engulfing | Big red candle swallowed previous green candle |
| Micro sweep | Small stop hunt on 15m before the real move |

Also checks:
- Is price above EMA20 on 15m for longs
- Is volume above average
- Is there a micro sweep on 15m

If 15m confirms — use 15m price as entry.
If 15m does not confirm — use current 4H price but reduce score by 2 points.

---

## Step 13 — SL Calculation

SL is placed at the point where the trade thesis is completely broken.
Not a random ATR multiple — the actual invalidation point.

**Priority order for SL:**

| Priority | Level | Logic |
|----------|-------|-------|
| 1st | Below retest zone bottom + ATR×0.15 buffer | If price closes below where the setup formed, setup is invalid |
| 2nd | Below sweep low + ATR×0.1 buffer | If price goes below where smart money hunted stops, they are not defending |
| 3rd | Beyond swing point + ATR×0.1 buffer | Structural invalidation |
| 4th | ATR × regime multiplier | Fallback only |

**ATR multiplier by market condition:**
| Regime | Multiplier |
|--------|-----------|
| Expansion | 2.5x |
| Trending | 2.0x |
| Weak Trend | 1.5x |

---

## Step 14 — TP Calculation

Single TP — no split position.

TP is placed at the nearest real resistance or support level
that is at least the grade multiplier distance away.

**Grade multipliers:**
| Grade | TP Multiplier |
|-------|--------------|
| A+ | 2.5x risk distance |
| A | 2.0x risk distance |
| B | 1.5x risk distance |

**Structure levels checked:**
- Swing highs/lows
- Previous day high/low
- Previous week high/low
- Volume Area High/Low

If nearest structure is closer than the multiplier minimum — use the minimum.
If nearest structure is further — use the structure level.

This gives realistic targets based on actual market structure
while ensuring minimum acceptable reward.

---

## Step 15 — Risk Sizing

How much of the position to take:

```
Risk amount = Capital × grade risk percentage
Position size = Risk amount ÷ SL percentage
Margin used = Position size ÷ leverage
```

**Grade risk percentages:**
| Grade | Risk % |
|-------|--------|
| A+ | 2% of capital |
| A | 1.5% of capital |
| B | 1% of capital |

Higher grade = slightly bigger position.
Lower grade = smaller position.
B grades risk less because they are lower quality setups.

---

## Step 16 — ML Gate Check

If ML is enabled (100+ closed trades exist and model is trained):

The signal's 16 factor scores are fed into the LightGBM model.
The model returns a win probability between 0 and 1.

```
Probability >= 0.65 → signal passes → forwarded to Freqtrade
Probability < 0.65  → signal filtered → not forwarded
```

If ML is not yet enabled (below 100 trades):
All A+/A/B signals that pass the grade filter are forwarded.

The ML probability is shown on the dashboard radar card,
in the Telegram signal alert, and in the coin analysis modal.

---

## Step 17 — Signal Written To Redis

If the signal passes all gates it is written to Redis.

```
Key: signal:{coin}USDT
TTL: 900 seconds (15 minutes)
```

**Payload written:**
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

Freqtrade reads this key every 4H candle close.
If valid and grade is A+/A/B — it enters the trade.

---

## Step 18 — Content Pipeline Triggered

For A+ and A signals only — the content pipeline fires asynchronously.
This does not block the scan. It runs in the background.

**Step 1 — Chart generated:**
mplfinance draws a 4H candlestick chart of the last 50 candles.
Entry, SL, and TP lines are drawn.
Sweep zone is shaded yellow.
Grade badge, score, direction label, and Signal Engine watermark added.
Saved as PNG 1200×675 pixels.

**Step 2 — Groq writes a post draft:**
Signal data including thesis, factor scores, entry/SL/TP, regime, session
is sent to llama-3.3-70b via Groq API.
Model writes a Twitter post under 280 characters.
Also writes a longer form version.
Tone rotates: 70% professional, 20% educational, 10% humor.

**Step 3 — Telegram approval sent:**
You receive the chart image followed by a message:

```
📝 New Signal Post Ready

AVAXUSDT SHORT — Grade A · Score 71/100
Tone: professional

Twitter Draft ✅ 241/280:

AVAX swept weekly highs and showed strong bearish
displacement. Confluence 71/100 with trending bearish
regime. Entry 6.32 | SL 6.80 | TP 5.90

#AVAX #CryptoTrading #SignalEngine

[✅ Approve & Post] [❌ Discard]
[✏️ Edit Draft]     [🔄 Regenerate]
```

You tap one button. That is all.

---

## Step 19 — Freqtrade Executes The Trade

Freqtrade runs its bot loop every 4H candle close.
It calls `populate_entry_trend()` which reads the Redis signal.

If signal is valid and not expired:
- Sets enter_long = 1 or enter_short = 1 on the last candle
- Freqtrade places a limit order at the signal entry price
- `confirm_trade_entry()` runs a final check:
  - Signal still in Redis and not expired
  - Entry price within 0.5% of current price
  - Grade is A+, A, or B
  - If any check fails — trade rejected

If trade opens:
- `custom_stoploss()` sets SL at the signal stoploss price
- `custom_exit()` monitors for TP hit or signal invalidation

**Exit conditions:**
| Condition | Action |
|-----------|--------|
| Current price reaches TP | Exit with tp_hit reason |
| Signal grade becomes F | Exit with signal_invalidated reason |
| Signal expires from Redis | Exit with signal_expired reason |

---

## Step 20 — What Comes To Your Telegram

You receive a signal alert like this:

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
✔ Liquidity swept at Weekly High Sweep — 2 candles ago
✔ Strong displacement bearish — 2.3x ATR range, vol 1.9x
✔ BTC bearish — confirms direction
⚠ OI exhaustion signal — momentum may be fading

Signal forwarded to Freqtrade for execution.
```

With two buttons:
- 📊 Factors — see all 16 scores
- ⚠️ Risks — see what could go wrong

---

## Step 21 — Outcome Sync

Every 30 minutes the scheduler runs `sync_freqtrade_outcomes()`.

It reads all closed trades from Freqtrade API.
For each closed trade it finds the matching Signal record by:
- Same coin
- Same direction
- Entry price within 2% tolerance
- Closest timestamp match

When matched:
- Signal.outcome updated to win or loss
- Signal.pnl updated with actual PnL
- Signal.exit_price updated

This is what feeds the ML training pipeline.
Without this sync the ML has no labels to learn from.

---

## Step 22 — ML Training (After 100 Trades)

When 100 closed signals exist in the Signal table:

The scheduler's hourly ML check detects eligibility.
`train_model()` is called automatically.

**Feature matrix built from:**
- All 16 factor scores stored in factor_scores JSON column
- sweep_score, retest_score, disp_score
- btc_score, market_score, entry_score
- overall score, funding rate
- grade encoded as number
- regime encoded as number
- session encoded as number
- direction encoded as +1 or -1

**Label:** win=1 loss=0

**Training:**
- LightGBM classifier with 200 estimators
- 5-fold cross validation
- Class weights balanced for win/loss ratio
- Model saved to ml/models/lgbm_model.pkl

**After training:**
- cfg.ML_ENABLED flips to True
- All future signals run through predictor
- Telegram notification sent with model stats and top features

**Retraining:**
Every 50 new closed trades the model retrains on the full dataset.
Gets smarter over time as more data accumulates.

---

## Step 23 — Commentary Posts (No Signal Scans)

When a scan completes with no tradeable signals:

The commentary pipeline checks if conditions are interesting enough to post about.

**Triggers:**
- Fear and greed below 20 (extreme fear)
- Fear and greed above 80 (extreme greed)
- 70%+ of coins in choppy regime
- Average funding above 0.06%
- Weekend market

**Cooldown by session:**
| Session | Cooldown |
|---------|---------|
| London/NY Overlap | 1 hour |
| London or NY | 2 hours |
| Asia | 6 hours |
| Weekend | 8 hours |

If triggered, Groq writes a market commentary post.
Tone is 40% humor — dry wit, crypto meme energy, relatable observations.

Examples:
```
"Market regime: choppy. ADX: 12. Translation: nobody knows anything right now. #Crypto"

"Funding at 0.09%. Someone out there is very confident. History suggests otherwise. #Bitcoin"

"It's Sunday. Liquidity left the building. Stop hunts incoming. You have been warned. #CryptoTrading"
```

Sent to Telegram for your approval before posting.

---

## The Complete Journey — One Line Per Step

| Step | What Happens |
|------|-------------|
| 1 | Alarm fires every 15 minutes |
| 2 | Reads market data from Redis (Freqtrade pushed it) or Binance fallback |
| 3 | Cleans bad candle data |
| 4 | Calculates all indicators on 4 timeframes |
| 5 | Runs 4 ICT engine checks — sweep, displacement, retest, order blocks |
| 6 | Detects market regime |
| 7 | Bouncer checks hard blocks — choppy, news, extreme funding, wrong session |
| 8 | Scores all 16 confluence factors |
| 9 | Calculates final score out of 100 |
| 10 | Assigns grade A+ to F |
| 11 | B grade runs additional quality filter |
| 12 | Decides direction LONG or SHORT |
| 13 | Refines entry on 15 minute chart |
| 14 | Calculates structure-aware SL |
| 15 | Calculates single TP with grade multiplier |
| 16 | Sizes position by grade risk percentage |
| 17 | ML gate checks win probability if model is trained |
| 18 | Writes signal to Redis for Freqtrade |
| 19 | Content pipeline generates chart and Groq draft |
| 20 | Telegram approval sent for Twitter post |
| 21 | Freqtrade reads Redis and executes trade on Binance |
| 22 | You receive full signal alert on Telegram |
| 23 | Sync job matches Freqtrade outcome back to Signal table |
| 24 | After 100 trades LightGBM trains and filters future signals |
| 25 | Commentary posts generated when market is interesting but no signals |

---

> Signal Engine is not a bot that buys when RSI is low and sells when RSI is high.
>
> Every signal has a reason — a story.
> Sweep happened here. Institutions displaced price there.
> Retest gave entry here. Structure says direction is this way.
> BTC agrees. Volume confirms. ML says 73% probability.
>
> When enough of those pieces align at the same time — that is the signal.
> That is the edge. Not any single indicator.
> The alignment of all of them together.
>
> The ML layer learns which specific combinations of those alignments
> actually produce winning trades in real market conditions.
> Over time the system gets smarter about its own signals.
