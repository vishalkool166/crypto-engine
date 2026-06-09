## How A Trade Is Born — Complete Journey

### The Big Picture First

Think of the app like a very strict hiring manager.
Every 15 minutes it interviews 13 coins.
Most get rejected immediately.
A few pass the first round.
Even fewer pass all rounds.
Only the best of the best get hired — meaning a trade opens.

---

## Step 1 — The Alarm Clock

Every 15 minutes a scheduler fires at exactly :00, :15, :30, :45 UTC.

Think of it like a school bell.
When the bell rings, the app wakes up and says
"okay time to check all 13 coins."

It goes through them in order:
BTC → ETH → BNB → SOL → XRP → ADA → AVAX → LINK → DOT → DOGE → LTC → ATOM → POL

Maximum 3 coins analyzed at the same time to not overload Binance API.

---

## Step 2 — Fetching The Raw Data

For each coin the app goes to Binance and downloads:

| What It Downloads | Why |
|------------------|-----|
| Weekly candles (1W) — last 500 | Big picture trend |
| Daily candles (1D) — last 1000 | Medium trend |
| 4 Hour candles (4H) — last 2000 | Entry zone |
| 1 Hour candles (1H) — last 1000 | Fine detail |
| 15 Minute candles (15M) — last 200 | Exact entry timing |
| Current price | Live market |
| Funding rate | Is market too crowded |
| Open interest | Is smart money entering or leaving |
| Long/short ratio | Is everyone on same side |
| Fear and greed index | Overall market mood |
| News filter | Any big economic events today |

Think of candles like a history book.
Each candle is one chapter — it tells you what price did
during that time period — where it opened, highest it went,
lowest it went, where it closed.

---

## Step 3 — Data Cleaning

Before doing anything with the data the app checks it is not garbage.

| Check | What It Catches |
|-------|----------------|
| Missing candles | Gaps in history |
| Duplicate candles | Same candle twice |
| High lower than low | Impossible price data |
| Zero prices | Exchange glitch |
| Extreme moves over 50% | Data error not real move |

If data is too dirty the coin gets skipped entirely.
Better to miss a signal than trade on bad data.

---

## Step 4 — Running The Indicators

Now the app calculates all the technical indicators on the clean data.

Think of indicators like different doctors examining the same patient.
Each one looks at a different thing and gives their opinion.

| Indicator | What It Tells Us | Simple Explanation |
|-----------|-----------------|-------------------|
| EMA 20, 50, 200 | Trend direction | Is price above or below its average |
| RSI | Momentum | Is the move getting tired or still strong |
| MACD | Momentum direction | Is buying or selling pressure growing |
| ATR | Volatility | How much does price normally move per day |
| ADX | Trend strength | Is there actually a trend or just noise |
| Bollinger Bands | Volatility range | Is price squeezed or expanding |
| Swing highs/lows | Structure | Where did price reverse before |
| Volume profile | Interest zones | Where did most trading happen |
| CVD | Buying vs selling | Are buyers or sellers actually in control |

This runs on all 4 timeframes — weekly, daily, 4H, 1H.
So the app has 4 complete pictures of the same coin at different zoom levels.

---

## Step 5 — The Four Engine Checks

Before scoring anything the app runs 4 specific checks.
These are the core ICT concepts the system is built on.

---

### Engine 1 — Liquidity Sweep Detection

**What is a liquidity sweep in simple terms:**

Imagine a swimming pool.
Everyone puts their stop losses just below the pool edge.
Big players — banks, institutions, whales — they know where those stops are.
They push price down briefly to trigger all those stops,
collect all that liquidity, then reverse and go up hard.

That brief dip below the edge is called a liquidity sweep.

**What the app checks:**
- Did price dip below a key level (previous day low, weekly low, swing low)
- Did it immediately come back above that level
- How strong was the move (ATR multiple)
- How much volume was on that candle
- How recent was it (last 5 candles = high relevance, 20 candles = expired)

**Score: 0 to 12**

---

### Engine 2 — Displacement Detection

**What is displacement in simple terms:**

After the sweep happens, the big players have collected their liquidity.
Now they push price hard in the real direction.
This hard push is called displacement — a big strong candle that moves fast.

Think of it like a slingshot.
The sweep pulls the rubber band back (fake move down).
Displacement is when they let go (real move up).

**What the app checks:**
- Was there a candle bigger than 1.5x the normal daily range
- Did the candle body take up more than 60% of the candle range (strong, not wicky)
- Did price close beyond the previous candle high (broke structure)
- Was volume higher than normal on that candle

**Score: 0 to 11**

---

### Engine 3 — Retest Detection

**What is a retest in simple terms:**

After the big displacement candle, price often comes back to test
the zone where it launched from.
This is your entry opportunity.

Think of it like a rocket launch.
The rocket blasts off (displacement).
Before going to the moon it briefly dips back toward the launch pad (retest).
That brief dip back is where you want to get on board.

**What the app checks:**
- Is there a valid zone to retest — Order Block, Fair Value Gap, or EMA
- Is price currently inside that zone
- Did price show a rejection candle inside the zone (hammer, engulfing)
- Was volume absorbed (selling dried up inside the zone)

**Zone priority:**
1. Order Block — where institutions placed big orders
2. Fair Value Gap — price moved so fast it left a gap
3. EMA 20 or 50 — dynamic support/resistance

**Score: 0 to 12**

---

### Engine 4 — Order Block Detection

**What is an order block in simple terms:**

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

## Step 6 — Market Regime Detection

Before scoring the signal the app asks one big question:
**Is this even a tradeable market right now?**

| Regime | What It Means | Tradeable |
|--------|--------------|-----------|
| Trending Bullish | Strong uptrend, ADX above 25 | ✅ Yes |
| Trending Bearish | Strong downtrend, ADX above 25 | ✅ Yes |
| Volatility Expansion | Big breakout happening | ✅ Yes |
| Weak Trend | ADX developing, 18-25 | 🟡 Reduced confidence |
| Ranging | Flat, narrow Bollinger Bands | ❌ No |
| Choppy | ADX below 18 on both 1D and 4H | ❌ Hard blocked |

Think of regime like weather.
You only go sailing in good weather.
Choppy market = storm = stay home.

---

## Step 7 — The No-Trade Engine

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
| Asian session | Low volume — fake moves |
| Already in a trade | One trade at a time |

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

## Step 8 — Scoring All 16 Confluence Factors

Now the real scoring happens.
Think of this like a judge scoring an Olympic gymnast.
Each judge scores one aspect.
All scores added up give the final result.

The app has 16 judges — each looking at one specific thing.

---

### The 16 Factors Explained Simply

**Why 16 factors?**
Because no single indicator is reliable alone.
When 12 out of 16 things align — that is a high probability setup.
When only 4 align — that is noise.

---

**Factor 1 — Liquidity Sweep (Weight: 12)**

Already calculated in Engine 1.
Highest weight because without a sweep there is no smart money footprint.
No sweep = no institutional involvement = no edge.

*What we learn: Did big players hunt stops before this move?*

---

**Factor 2 — Retest Confirmation (Weight: 12)**

Already calculated in Engine 3.
Equal highest weight because without a retest there is no entry point.
A sweep without a retest means you missed the entry.

*What we learn: Is price giving us a safe entry point right now?*

---

**Factor 3 — Displacement (Weight: 11)**

Already calculated in Engine 2.
Near highest weight because displacement confirms institutional intent.
Without displacement the move could be random noise.

*What we learn: Did institutions actually push price with conviction?*

---

**Factor 4 — Market Regime (Weight: 10)**

Is the overall market trending or choppy.
Full score if trending. Zero if choppy.

*What we learn: Is this a market worth trading at all?*

---

**Factor 5 — Weekly Filter (Weight: 10)**

Does the weekly trend agree with the daily trend.
Both bullish = full score.
Weekly neutral = half score.
Weekly conflicts daily = zero.

*What we learn: Is the big picture supporting this trade direction?*

---

**Factor 6 — Market Structure (Weight: 9)**

Is price making higher highs and higher lows (bullish structure)
or lower highs and lower lows (bearish structure).

*What we learn: Is the market organized in our direction?*

---

**Factor 7 — Session Timing (Weight: 8)**

What trading session is active right now.

| Session | Score | Why |
|---------|-------|-----|
| London/NY Overlap | 9/9 | Highest volume — best signals |
| New York | 7/9 | High volume — good signals |
| London | 7/9 | High volume — good signals |
| Asian | 2/9 | Low volume — fake moves |

Also checks if current volume is above 60% of session average.
Low volume session = downgrade quality regardless of time.

*What we learn: Is there enough real participation for this signal to work?*

---

**Factor 8 — BTC Alignment (Weight: 8)**

For every coin except BTC itself —
is Bitcoin trending in the same direction.

Checks both 1D and 4H BTC trend.
Both must agree for full score.
1D bull but 4H already flipping bear = half score only.

*What we learn: Is the market leader supporting or fighting this trade?*

---

**Factor 9 — OI Behavior (Weight: 7)**

Open interest = total number of active contracts.

| Scenario | Meaning |
|----------|---------|
| Price up + OI up | Real buying — institutions entering longs |
| Price down + OI up | Real selling — institutions entering shorts |
| Price up + OI down | Short covering — weaker move |
| OI exhaustion | Momentum fading |

*What we learn: Is smart money actually entering or is this just retail?*

---

**Factor 10 — Volume Expansion (Weight: 7)**

Is current volume higher than the 5-period average.
Above 1.5x average = full score.
Above 0.85x = partial score.
Below = zero.

*What we learn: Is there real participation behind this move?*

---

**Factor 11 — Funding Rate (Weight: 6)**

Funding rate is a fee paid between longs and shorts every 8 hours.
High positive funding = too many longs = squeeze risk.
High negative funding = too many shorts = squeeze risk.

| Funding | Score |
|---------|-------|
| Below 0.05% | Full score — neutral |
| 0.05-0.08% | Partial — elevated |
| Above 0.08% | Zero — hard block |

*What we learn: Is the market too crowded in one direction?*

---

**Factor 12 — RSI Divergence (Weight: 4)**

Divergence is when price and RSI disagree.

| Type | Meaning |
|------|---------|
| Bullish divergence | Price made lower low but RSI made higher low — hidden strength |
| Bearish divergence | Price made higher high but RSI made lower high — hidden weakness |
| Hidden bull | Price higher low, RSI lower low — trend continuation |
| Hidden bear | Price lower high, RSI higher high — trend continuation down |

*What we learn: Is momentum secretly building or secretly fading?*

---

**Factor 13 — Order Blocks (Weight: 4)**

Already calculated in Engine 4.
Is price in or approaching a valid order block zone.

*What we learn: Are we entering at an institutional level?*

---

**Factor 14 — ATR Volatility (Weight: 3)**

ATR as percentage of price should be between 0.5% and 5%.
Too low = dead market, no movement.
Too high = chaotic, unpredictable.

*What we learn: Is volatility in a tradeable range?*

---

**Factor 15 — RSI Context (Weight: 2)**

For a long trade — RSI should be between 40 and 75.
Not oversold (already bounced) and not overbought (exhausted).
For a short trade — RSI between 25 and 60.

*What we learn: Is momentum in a healthy zone for entry?*

---

**Factor 16 — MACD Histogram (Weight: 1)**

Is the MACD histogram positive and expanding for longs.
Negative and expanding for shorts.
Lowest weight because it is a lagging confirmation only.

*What we learn: Is momentum mathematically confirmed in our direction?*

---

## Step 9 — Calculating The Final Score

All 16 factor scores are added up.

```
Total earned points / Maximum possible points × 100 = Score out of 100
```

Maximum possible = 118 points across all 16 factors.

Then soft block penalties are subtracted.

```
Score after penalties = Final score
```

---

## Step 10 — Grading

| Score | Grade | Action |
|-------|-------|--------|
| 85-100 | A+ | Auto-execute trade |
| 68-84 | A | Auto-execute trade |
| 52-67 | B | Skip |
| 38-51 | C | Watch — setup building |
| 0-37 | F | Hard blocked |

---

## Step 11 — Direction Decision

If grade is A or A+ the app decides direction:

| Condition | Direction |
|-----------|----------|
| 1D bullish AND 4H bullish | LONG |
| 1D bearish AND 4H bearish | SHORT |
| Conflict | No trade |

Simple rule — both timeframes must agree.

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

**Two candle confirmation required:**
Pattern candle must be confirmed by next candle not reversing it.
One candle alone is not enough.

Also checks:
- Is price above EMA20 on 15m for longs
- Is volume above average
- Is there a micro sweep on 15m (mini liquidity grab)

If 15m confirms — use 15m price as entry.
If 15m does not confirm — use current 4H price but reduce score by 5 points.

---

## Step 13 — SL/TP Calculation

### Stop Loss — Where Is The Trade Wrong

SL is placed at the point where the trade thesis is completely broken.
Not a random ATR multiple — the actual invalidation point.

**Priority order for SL:**

| Priority | Level | Logic |
|----------|-------|-------|
| 1st | Below retest zone bottom + small buffer | If price closes below where the setup formed, setup is invalid |
| 2nd | Below sweep low | If price goes below where smart money hunted stops, they are not defending |
| 3rd | Beyond swing point | Structural invalidation |
| 4th | ATR × regime multiplier | Fallback only |

**ATR multiplier by market condition:**
- Expansion market = 2.5x ATR — volatile, needs room
- Trending market = 2.0x ATR — standard
- Weak trend = 1.5x ATR — tighter is fine

Minimum SL distance enforced at 1.2% — prevents SL too tight to survive normal wicks.

### Take Profit — Where Is The Next Wall

TP is placed at the next real resistance or support level.
Not a fixed 1.5R or 2.5R multiple — actual market structure.

**TP1 — nearest real level:**
Looks at swing highs/lows, previous day high/low,
Volume Area High/Low from volume profile.
Picks the nearest one that is at least 1.2R away.

**TP2 — next major structure:**
Looks at weekly levels, previous week high/low,
Point of Control from volume profile.
Picks the next level beyond TP1.

### Trade Split:
- 70% of position closes at TP1
- 30% of position runs to TP2
- When TP1 hits — SL moves to breakeven automatically
- Remaining 30% is now risk-free

---

## Step 14 — Risk Sizing

How much of the position to take:

```
Risk amount = Capital × dynamic risk percentage
Position size = Risk amount ÷ SL percentage
Margin used = Position size ÷ leverage
```

Dynamic risk percentage scales with score:
- Score 95+ → risk 13% of capital
- Score 85-94 → risk 10-13%
- Score 68-84 → risk 7-10%

Higher confidence = slightly bigger position.
Lower confidence = smaller position.

---

## Step 15 — Final Gates Before Trade Opens

Even after all this, three more checks:

| Gate | Check |
|------|-------|
| Daily trade count | Max 3 trades per day |
| Daily loss cap | If already lost 20% of capital today — stop |
| Entry price validation | Current price must be within 0.3% of signal entry — no stale signals |

All three must pass or trade is blocked.

---

## Step 16 — Trade Opens

If everything passes:

1. Set leverage to 10x on Binance
2. Place market order — fills immediately at current price
3. Place stop loss order at calculated SL
4. Place TP1 order for 70% of position
5. Place TP2 order for 30% of position
6. Save everything to database
7. Start live price feed via WebSocket
8. Send Telegram alert to you

---

## Step 17 — What Comes To Your Telegram

You receive a message like this:

```
🏆 Grade A+ — LONG
━━━━━━━━━━━━━━━━━━━━━━

BTCUSDT — 📈 LONG
Confidence: Very High (87/100)
Regime: TRENDING BULLISH
Session: London/NY Overlap
Time: 02:34 PM IST

━━━━━━━━━━━━━━━━━━━━━━
Entry:   $67,234.0000
SL:      $66,180.0000 (1.57%)
TP1:     $68,890.0000
TP2:     $70,450.0000

━━━━━━━━━━━━━━━━━━━━━━
Risk:    $1.00
Size:    $100.00
Lev:     10x

Why This Trade?
✔ Market structure bullish — structure and trend aligned
✔ Liquidity swept at Swing Low Sweep — 3 candles ago
✔ Strong displacement bullish — 2.1x ATR range, vol 1.8x
✔ Retest confirmed at 4H Order Block — Bullish engulfing
✔ BTC bullish — confirms direction
✔ OI confirming — OI bullish confirm
```

With two buttons:
- 📊 Show Factors — see all 16 scores
- ⚠️ Show Risks — see what could go wrong

---

## Step 18 — While Trade Is Open

Every 1 minute the health engine runs silently:

| Check | What It Looks For |
|-------|------------------|
| Retest zone | Did price close below the zone it launched from |
| Structure | Did a bearish BOS form against the long |
| BTC | Did BTC flip bearish strongly |
| OI | Is OI showing exhaustion |
| Price vs ATR | How far adverse from entry |
| Order block | Was the entry OB mitigated |

You get alerts at:
- 25% progress to TP1
- 50% progress to TP1
- 75% progress to TP1
- TP1 hit — SL moved to breakeven
- Health state change — HEALTHY → WARNING → INVALIDATED

---

## Step 19 — Trade Closes

Four ways a trade closes:

| Reason | Outcome |
|--------|---------|
| SL hit | Loss — full position stopped out |
| TP1 hit then BE SL hit | Win — locked in partial profit |
| TP2 hit | Full win — maximum profit |
| Manual close via /close | Manual — your decision |

After close you receive:
- Close alert with PnL
- Post-trade debrief — what worked, what to watch next time
- Grade accuracy update

---

## The Complete Journey — One Line Summary Per Step

| Step | What Happens |
|------|-------------|
| 1 | Alarm fires every 15 minutes |
| 2 | Downloads all price data from Binance |
| 3 | Cleans bad data |
| 4 | Calculates all indicators |
| 5 | Runs 4 ICT engine checks |
| 6 | Detects market regime |
| 7 | Bouncer checks hard blocks |
| 8 | Scores all 16 confluence factors |
| 9 | Calculates final score out of 100 |
| 10 | Assigns grade A+ to F |
| 11 | Decides direction LONG or SHORT |
| 12 | Refines entry on 15 minute chart |
| 13 | Calculates structure-aware SL and TP |
| 14 | Sizes position by risk percentage |
| 15 | Final gates — daily cap, trade count, price validation |
| 16 | Opens trade on Binance paper account |
| 17 | Sends full alert to your Telegram |
| 18 | Monitors health every minute |
| 19 | Closes trade and sends debrief |

> This is not a bot that buys when RSI is low and sells when RSI is high.
> Every trade has a reason — a story — sweep happened here,
> institutions displaced price there, retest gave entry here,
> structure says direction is this way, BTC agrees, volume confirms.
> When enough of those pieces align at the same time — that is the signal.
> That is the edge. Not any single indicator. The alignment of all of them together.