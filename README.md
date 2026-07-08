```markdown
# Signal Engine v5

<div align="center">

![Signal Engine](https://img.shields.io/badge/Signal_Engine-v5.0-00ff88?style=for-the-badge&logoColor=white)
[![Live Demo](https://img.shields.io/badge/🔴_LIVE-signal--engine--v5.vishalkool.top-00ff88?style=for-the-badge)](https://signal-engine-v5.vishalkool.top)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![Docker](https://img.shields.io/badge/Docker-Deployed-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![AWS](https://img.shields.io/badge/AWS-EC2-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)](https://aws.amazon.com)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![LightGBM](https://img.shields.io/badge/LightGBM-ML_Gate-9B59B6?style=for-the-badge)](https://lightgbm.readthedocs.io)

**Automated crypto futures intelligence engine built on Binance Futures.**

*Combines ICT concepts, multi-timeframe confluence scoring, and smart money principles into a fully automated trading system with real-time dashboard, Telegram control, Twitter content pipeline, and LightGBM ML gate.*

[🔴 Live Demo](https://signal-engine-v5.vishalkool.top) · [📁 Portfolio Code](https://github.com/vishalkool166/signal-engine-portfolio) · [📄 Resume](https://github.com/vishalkool166/signal-engine-portfolio/blob/main/RESUME.md)

</div>

---

## 🧠 What Is This?

Signal Engine v5 is a **fully autonomous crypto futures trading intelligence platform** that thinks, decides, and acts — 24 hours a day, 7 days a week.

It doesn't just show charts. It **reads the market** using institutional trading concepts, scores every opportunity across 16 dimensions, filters with machine learning, and executes trades on Binance Futures — all without human intervention.

> *"Every signal has a reason — a story. Sweep happened here. Institutions displaced price there. Retest gave entry here. Structure says direction is this way. BTC agrees. Volume confirms. ML says 73% probability. When enough of those pieces align at the same time — that is the signal."*

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      BINANCE FUTURES API                     │
│         OHLCV · Ticker · Funding · OI · Long/Short          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                        REDIS LAYER                           │
│              Shared real-time data nervous system            │
│   candles:{coin}:{tf} · ticker · funding · oi · ls_ratio    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    SIGNAL ENGINE BRAIN                       │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Data Fetcher│  │  Indicators  │  │  Regime Detector  │  │
│  │ Redis-first │  │ EMA·RSI·MACD │  │ Trend·Range·Chop  │  │
│  └──────┬──────┘  └──────┬───────┘  └─────────┬─────────┘  │
│         └────────────────┼──────────────────────┘           │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              4 ENGINE CHECKS (ICT Concepts)           │  │
│  │  💧 Liquidity Sweep  ⚡ Displacement                  │  │
│  │  🎯 Retest Zone      📦 Order Blocks                  │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         16-FACTOR CONFLUENCE SCORER (0-100)           │  │
│  │  Score = Σ(factor_earned) / max_possible × 100        │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              SIGNAL GRADING ENGINE                    │  │
│  │   A+ (85+) · A (68+) · B (52+) · C (38+) · F (<38)   │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │           LIGHTGBM ML GATE (after 100 trades)         │  │
│  │      Win probability ≥ 65% → PASS · < 65% → BLOCK    │  │
│  └───────────────────────┬───────────────────────────────┘  │
└──────────────────────────┼──────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
┌──────────────┐  ┌────────────────┐  ┌──────────────────┐
│   BINANCE    │  │    TELEGRAM    │  │  TWITTER/X API   │
│   FUTURES    │  │   BOT ALERTS  │  │  AI Content Post  │
│  EXECUTION   │  │  30+ Commands  │  │  Groq LLM Writer  │
└──────────────┘  └────────────────┘  └──────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                   REACT DASHBOARD (PWA)                      │
│         WebSocket push · Real-time PnL · Signal Radar        │
│         Multi-tier SaaS · Google OAuth · Mobile Ready        │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚡ How A Signal Is Born

```
Every 15 minutes (:00 :15 :30 :45 UTC)
         │
         ▼
Fetch market data from Redis (Binance fallback)
         │
         ▼
Clean + validate candle data
         │
         ▼
Calculate indicators on 4 timeframes (1W · 1D · 4H · 1H)
         │
         ▼
Run 4 ICT engine checks
  ├── 💧 Liquidity Sweep — Did big players hunt stops?
  ├── ⚡ Displacement — Did institutions push price hard?
  ├── 🎯 Retest — Is price returning to launch zone?
  └── 📦 Order Blocks — Are we near institutional level?
         │
         ▼
Detect market regime
  ├── TRENDING BULLISH/BEARISH → Tradeable ✅
  ├── RANGING → Reduced confidence ⚠️
  └── CHOPPY → Hard blocked ❌
         │
         ▼
Score 16 confluence factors (0-100)
         │
         ▼
Grade signal: A+ · A · B · C · F
         │
         ▼
ML Gate check (if 100+ closed trades exist)
  ├── Win probability ≥ 65% → PASS ✅
  └── Win probability < 65% → BLOCKED ❌
         │
         ▼
Calculate structure-aware SL + TP
         │
         ▼
Execute on Binance Futures via CCXT
         │
         ▼
Push to dashboard via WebSocket
Send Telegram alert
Trigger Twitter content pipeline
```

---

## 📊 Signal Grading System

| Grade | Score | Action | Risk | TP Multiplier |
|-------|-------|--------|------|---------------|
| 🏆 **A+** | 85-100 | Auto-execute | 2% capital | 2.5x risk |
| ✅ **A** | 68-84 | Auto-execute | 1.5% capital | 2.0x risk |
| 👀 **B** | 52-67 | Paper only + quality filter | 1% capital | 1.5x risk |
| ⏳ **C** | 38-51 | Watch — setup building | Never | — |
| 🚫 **F** | 0-37 | Hard blocked | Never | — |

### Grade B Quality Filter
B grades only execute in paper mode when **ALL** pass:
- ✅ Market score ≥ 65
- ✅ London or NY session active
- ✅ BTC score ≥ 4 (not conflicting)
- ✅ Maximum 1 hard block present

---

## 🎯 16 Confluence Factors

```
┌─────────────────────────────────────────────────────────────┐
│                  CONFLUENCE SCORING ENGINE                   │
├──────────────────────────┬──────────┬───────────────────────┤
│ Factor                   │ Weight   │ What It Checks        │
├──────────────────────────┼──────────┼───────────────────────┤
│ 💧 Liquidity Sweep       │   12     │ Stop hunt confirmed   │
│ 🎯 Retest Confirmation   │   12     │ Price in OB/FVG/EMA   │
│ ⚡ Displacement          │   11     │ Impulsive move away   │
│ 📈 Market Regime         │   10     │ Trend/range/chop      │
│ 📅 Weekly Filter         │   10     │ Weekly+daily aligned  │
│ 🏗️ Market Structure      │    9     │ BOS/CHoCH bias        │
│ 🕐 Session Timing        │    8     │ London/NY quality     │
│ ₿  BTC Alignment         │    8     │ BTC 1D+4H confirms    │
│ 📊 OI Behavior           │    7     │ Open interest dir     │
│ 📢 Volume Expansion      │    7     │ Volume above MA       │
│ 💸 Funding Extreme       │    6     │ Squeeze risk filter   │
│ 📉 RSI Divergence        │    4     │ Hidden/regular div    │
│ 📦 Order Blocks          │    4     │ ICT OB proximity      │
│ 📏 ATR Volatility        │    3     │ Tradeable range       │
│ 🔢 RSI Context           │    2     │ Not overbought/sold   │
│ 📊 MACD Histogram        │    1     │ Momentum expanding    │
├──────────────────────────┼──────────┼───────────────────────┤
│ TOTAL MAX POSSIBLE       │  114     │                       │
└──────────────────────────┴──────────┴───────────────────────┘

Score = (Total Earned / 114) × 100
```

---

## 🤖 LightGBM ML Gate

```
┌─────────────────────────────────────────────────────────────┐
│                    ML GATE PIPELINE                          │
│                                                              │
│  TRAINING DATA                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 16 factor scores + regime + session + direction     │    │
│  │ + sweep/retest/disp scores + BTC score + funding    │    │
│  │ + grade + slippage + commission + hold duration     │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│                         ▼                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           LightGBM Binary Classifier                │    │
│  │  Label: win=1 loss=0                                │    │
│  │  CV: 5-fold StratifiedKFold                         │    │
│  │  Class weights: balanced for win/loss ratio         │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│                         ▼                                    │
│  ACTIVATION RULES                                            │
│  ├── Below 100 trades → All A+/A/B signals pass             │
│  ├── After 100 trades → ML gate activates                   │
│  ├── Probability ≥ 0.65 → Signal PASSES ✅                  │
│  ├── Probability < 0.65 → Signal BLOCKED ❌                 │
│  └── Auto-retrains every 50 new closed trades               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🐦 Content Pipeline

```
A+/A Signal Generated
         │
         ▼
┌────────────────────┐
│  Chart Generated   │
│  mplfinance 4H     │
│  Entry·SL·TP lines │
│  Sweep zone shaded │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│   Groq LLM Writes  │
│   llama-3.3-70b    │
│   Tone rotation:   │
│   70% professional │
│   20% educational  │
│   10% humor        │
└────────┬───────────┘
         │
         ▼
┌────────────────────────────────────────┐
│         Telegram Approval              │
│                                        │
│  📊 Chart image sent                  │
│  📝 Draft post sent                   │
│                                        │
│  [✅ Approve & Post]  [❌ Discard]    │
│  [✏️ Edit Draft]      [🔄 Regenerate] │
└────────┬───────────────────────────────┘
         │ Approved
         ▼
┌────────────────────┐
│   Twitter/X Post   │
│   Engagement track │
└────────────────────┘
```

---

## 🛠️ Tech Stack

### Backend
| Layer | Technology | Purpose |
|-------|-----------|---------|
| Language | Python 3.11+ | Core runtime |
| API | FastAPI + Uvicorn | REST + WebSocket server |
| Data Layer | Redis 7 | Real-time market data cache |
| Database | SQLite + SQLAlchemy | Signal + trade persistence |
| Exchange | Binance Futures via CCXT | Market data + execution |
| Scheduling | APScheduler | 15-min scan jobs |
| Indicators | TA-Lib, Pandas, NumPy | Technical analysis |
| ML | LightGBM + scikit-learn | Signal win probability |
| Alerts | Telegram Bot API + HTTPX | Real-time notifications |
| Content | Groq llama-3.3-70b | AI post generation |
| Charts | mplfinance | Signal chart images |
| Social | Tweepy | Twitter/X posting |
| Auth | PyOTP + bcrypt + JWT | TOTP + session security |

### Frontend
| Layer | Technology | Purpose |
|-------|-----------|---------|
| Framework | React 18 + TypeScript | UI runtime |
| Build | Vite + PWA | Fast builds + mobile app |
| Styling | TailwindCSS | Utility-first CSS |
| Animation | Framer Motion | Smooth transitions |
| Data | TanStack Query | Server state management |
| State | Zustand | Client state |
| Charts | Recharts | Performance visualization |
| Components | Radix UI | Accessible primitives |
| Auth | Google OAuth | User authentication |

### Infrastructure
| Layer | Technology | Purpose |
|-------|-----------|---------|
| Server | AWS EC2 t3.small | 24/7 hosting |
| Containers | Docker + Compose | Service orchestration |
| Proxy | Nginx | SSL + reverse proxy |
| SSL | Let's Encrypt | HTTPS certificate |
| Deploy | Git cron watcher | Auto-deploy on push |

---

## 📁 Project Structure

```
signal-engine-portfolio/
│
├── 📂 backend/
│   ├── main.py              # FastAPI app · WebSocket · lifespan
│   ├── config.py            # Weights · constants · SaaS tiers
│   ├── database.py          # SQLAlchemy models · session mgmt
│   ├── scheduler.py         # APScheduler · scan · ML · sync
│   ├── auth.py              # JWT · TOTP · OAuth · sessions
│   ├── redis_client.py      # Redis connection singleton
│   ├── requirements.txt     # Python dependencies
│   │
│   ├── 📂 engines/          # ⚠️ Core intelligence
│   │   ├── indicators.py    # ✅ EMA · RSI · MACD · ATR · ADX
│   │   ├── capital.py       # ✅ Dynamic position sizing
│   │   ├── validator.py     # ✅ Candle data validation
│   │   └── PROPRIETARY.md  # 🔒 Confluence · Signal · Sweep
│   │                        #    Displacement · Retest · Regime
│   │                        #    OrderBlocks · Thesis
│   │
│   ├── 📂 ml/               # ⚠️ ML pipeline
│   │   └── PROPRIETARY.md  # 🔒 Trainer · Predictor · Dataset
│   │                        #    Eligibility checker
│   │
│   ├── 📂 alerts/
│   │   ├── telegram.py      # ✅ Bot commands · webhook · alerts
│   │   ├── briefing.py      # ✅ Morning/evening briefings
│   │   ├── utils.py         # ✅ Shared utilities
│   │   └── PROPRIETARY.md  # 🔒 Core scanner orchestration
│   │
│   ├── 📂 trade/
│   │   ├── exchange.py      # ✅ Binance CCXT integration
│   │   ├── executor.py      # ✅ Order placement + SL/TP
│   │   ├── monitor.py       # ✅ Position monitoring
│   │   ├── sync.py          # ✅ Outcome sync
│   │   └── ws.py            # ✅ WebSocket streams
│   │
│   ├── 📂 data/
│   │   ├── fetcher.py       # ✅ Redis-first + Binance fallback
│   │   ├── store.py         # ✅ Candle persistence
│   │   └── cache.py         # ✅ In-memory TTL cache
│   │
│   ├── 📂 api/
│   │   ├── routes.py        # ✅ All REST endpoints
│   │   ├── trading.py       # ✅ Trade management endpoints
│   │   └── dashboard.py     # ✅ Dashboard payload builders
│   │
│   ├── 📂 backtest/
│   │   ├── report.py        # ✅ Backtest report builder
│   │   └── factor_analysis.py # ✅ Factor edge analysis
│   │
│   └── 📂 content/
│       └── PROPRIETARY.md  # 🔒 Pipeline · Chart · Groq · Twitter
│
└── 📂 frontend/
    ├── 📂 src/
    │   ├── 📂 pages/        # 11 dashboard pages
    │   │   ├── Home.tsx     # Overview + KPIs + signal queue
    │   │   ├── Signals.tsx  # Signal radar + coin detail
    │   │   ├── Trades.tsx   # Live positions + history
    │   │   ├── Performance.tsx # Equity curve + factor analysis
    │   │   ├── Users.tsx    # Admin user management
    │   │   ├── Coins.tsx    # Coin universe management
    │   │   ├── System.tsx   # Infrastructure monitor
    │   │   ├── Audit.tsx    # Audit log
    │   │   ├── Settings.tsx # API keys + sessions
    │   │   ├── Profile.tsx  # Subscription + features
    │   │   └── Pricing.tsx  # SaaS pricing tiers
    │   │
    │   ├── 📂 components/
    │   │   ├── layout/      # Sidebar · TopBar · AuthGuard
    │   │   ├── modals/      # CommandPalette · TotpModal
    │   │   └── ui/          # KPICard · GradeTag · SpotlightCard
    │   │                    # DataTable · StatusBadge · EmptyState
    │   │
    │   ├── 📂 stores/       # Zustand state management
    │   │   ├── authStore.ts # User + tier + features
    │   │   ├── wsStore.ts   # WebSocket payload
    │   │   └── uiStore.ts   # Sidebar + UI state
    │   │
    │   └── 📂 types/        # Full TypeScript definitions
    │
    ├── package.json
    ├── vite.config.ts
    └── tailwind.config.ts
```

---

## 🌐 API Reference

### Signal Engine Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/dashboard` | Full dashboard payload |
| `GET` | `/api/dashboard/signals` | Signal radar + queue |
| `GET` | `/api/analyze/{coin}` | Single coin deep analysis |
| `GET` | `/api/scan` | Trigger manual scan |
| `GET` | `/api/signals` | Signal history with filters |
| `GET` | `/api/signals/active` | All valid Redis signals |
| `GET` | `/api/coins` | Coin universe |
| `POST` | `/api/coins/add` | Add coin + trigger backfill |
| `POST` | `/api/coins/toggle` | Enable/disable coin |
| `GET` | `/api/backtest/{coin}` | Run walk-forward backtest |
| `GET` | `/api/analysis/factors` | Factor edge analysis |
| `POST` | `/api/sync/outcomes` | Manual outcome sync |
| `POST` | `/api/mode/toggle` | Switch live/paper (TOTP) |
| `GET` | `/api/health` | System health + ML status |
| `GET` | `/api/audit/log` | Audit log |
| `WS` | `/ws/dashboard` | Real-time push every 2s |

---

## 🤖 Telegram Bot Commands

```
📊 STATUS          🔍 MARKET
/status            /btc
/mode              /coin ETH
/next              /regime
/session           /funding
                   /fear

📡 SIGNALS         📈 PERFORMANCE
/scan              /pnl
/queue             /history
/brief             /stats
/evening           /streak
                   /grade
                   /daily

🔬 ANALYSIS        🤖 ML
/backtest BTC      /ml
/factors           /sync
/debrief

📝 CONTENT
/pending
/brief
/discard N
```

---

## 🏢 SaaS Tier System

```
┌──────────┬──────────┬──────────┬──────────┐
│   FREE   │   PRO    │  ELITE   │  ADMIN   │
├──────────┼──────────┼──────────┼──────────┤
│ 30m delay│  Live    │  Live    │  Live    │
│ 3/day    │Unlimited │Unlimited │Unlimited │
│ Grade ✅ │ Grade ✅ │ Grade ✅ │ Grade ✅ │
│ Levels ❌│ Levels ✅│ Levels ✅│ Levels ✅│
│ ML ❌    │ ML ❌    │ ML ✅    │ ML ✅    │
│ Factors❌│Factors ❌│Factors ✅│Factors ✅│
│ API ❌   │ API ❌   │ API ✅   │ API ✅   │
│ 5 coins  │All coins │All coins │All coins │
└──────────┴──────────┴──────────┴──────────┘
```

---

## 🔒 Security

- **Google OAuth** — Secure user authentication
- **TOTP (2FA)** — Required for mode switching and dangerous actions
- **JWT Sessions** — Secure session management with device tracking
- **Rate Limiting** — All endpoints protected via slowapi
- **API Keys** — Programmatic access with prefix tracking
- **Audit Log** — Every action logged with IP and timestamp

---

## ⏱️ Scan Schedule

| Job | Schedule | Description |
|-----|----------|-------------|
| Coin scan | `:00/:15/:30/:45 UTC` | Full universe analysis |
| Morning briefing | `08:00 UTC` | London open summary |
| Evening briefing | `13:00 UTC` | NY open summary |
| Outcome sync | `Every 30 min` | Closed trade sync |
| ML check | `Every 1 hour` | Auto-train trigger |
| Engagement update | `Every 6 hours` | Twitter metrics |

---

## 🖥️ Infrastructure

```
AWS EC2 t3.small (2 vCPU · 2GB RAM)
│
├── Nginx (system service)
│   └── signal-engine-v5.vishalkool.top → :8000
│
└── Docker Compose
    ├── redis:7-alpine      (~50MB RAM)
    └── signal-engine       (~400MB RAM)
        ├── FastAPI backend
        ├── React frontend (served as static)
        └── All background jobs
```

---

## 🔒 Proprietary Components

The following contain core trading intelligence and are available for review during technical interviews:

| File | Contains |
|------|----------|
| `engines/confluence.py` | 16-factor weighted scoring engine |
| `engines/signal.py` | Signal generation + grading logic |
| `engines/sweep.py` | Liquidity sweep detection algorithm |
| `engines/displacement.py` | Institutional displacement detection |
| `engines/retest.py` | Retest zone confirmation engine |
| `engines/regime.py` | Market regime classification |
| `engines/orderblocks.py` | ICT order block detection |
| `ml/trainer.py` | LightGBM training pipeline |
| `ml/predictor.py` | Win probability prediction |
| `alerts/scanner.py` | Core scan orchestration |
| `content/pipeline.py` | AI content generation pipeline |

📧 **Contact for full review:** vishalkool166@gmail.com

---

## 🚀 Built With Prompt Engineering

This entire system — 50+ Python files, 70+ React components, full infrastructure — was **architected and built through structured prompt engineering** over 2 months.

No traditional software engineering background.
100% production deployed and running live.

This demonstrates the core skill of modern AI-augmented development:
- Knowing **what** to build
- Knowing **how** to structure it
- Directing AI to implement it correctly
- Debugging and deploying it to production

---

## 📞 Contact

<div align="center">

**Vishal Katike**

[![Email](https://img.shields.io/badge/Email-vishalkool166@gmail.com-D14836?style=for-the-badge&logo=gmail&logoColor=white)](mailto:vishalkool166@gmail.com)
[![Phone](https://img.shields.io/badge/Phone-+91_8978439995-25D366?style=for-the-badge&logo=whatsapp&logoColor=white)](tel:+918978439995)
[![Location](https://img.shields.io/badge/Location-Hyderabad,_India-FF9900?style=for-the-badge&logo=googlemaps&logoColor=white)](https://maps.google.com/?q=Hyderabad)

*Open to: Prompt Engineer · AI Product Analyst · AI Solutions Engineer · Technical AI Roles*

</div>

---

<div align="center">

*Built with Python + FastAPI + Redis + LightGBM + React + TypeScript and a lot of market structure reading.*

⭐ Star this repo if you found it interesting!

</div>
```