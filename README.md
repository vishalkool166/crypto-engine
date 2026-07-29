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
[![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-1C3C3C?style=for-the-badge)](https://langchain-ai.github.io/langgraph)
[![LangSmith](https://img.shields.io/badge/LangSmith-Tracing-FF6B35?style=for-the-badge)](https://smith.langchain.com)

**Automated crypto futures intelligence engine built on Binance Futures.**

*Combines ICT concepts, multi-timeframe confluence scoring, and smart money principles into a fully automated trading system — now powered by a RAG intelligence layer, LangGraph agent pipeline, and LangSmith AI observability.*

[🔴 Live Demo](https://signal-engine-v5.vishalkool.top) · [📁 Portfolio Code](https://github.com/vishalkool166/signal-engine-portfolio) · [📄 Resume](https://github.com/vishalkool166/signal-engine-portfolio/blob/main/RESUME.md)

</div>

---

## 🧠 What Is This?

Signal Engine v5 is a **fully autonomous crypto futures trading intelligence platform** that thinks, decides, and acts — 24 hours a day, 7 days a week.

It doesn't just show charts. It **reads the market** using institutional trading concepts, scores every opportunity across 16 dimensions, filters with machine learning, and executes trades on Binance Futures — all without human intervention.

In v5, the system gained a **RAG intelligence layer** — a retrieval-augmented generation pipeline that indexes all trade history, signals, and performance data into a vector store. You can now ask the system natural language questions and get answers grounded in your actual trading data.

The signal pipeline was also converted into a **LangGraph agent graph** — making every decision step visible, traceable, and observable through LangSmith AI tracing.

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
│  │         LANGGRAPH SIGNAL AGENT (NEW in v5)            │  │
│  │  context → sweep → zone → trigger → risk →           │  │
│  │  grade → ml_gate → finalize                          │  │
│  │  Each step is a node. Each decision is traced.       │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         16-FACTOR CONFLUENCE SCORER (0-100)           │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │           LIGHTGBM ML GATE (after 100 trades)         │  │
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
│              RAG INTELLIGENCE LAYER (NEW in v5)              │
│                                                              │
│  ChromaDB Vector Store · sentence-transformers embeddings    │
│  5 chunk types · LangChain retrieval · Groq LLM answers     │
│  Indexes: trades · signals · daily · coins · docs           │
└─────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│            LANGSMITH OBSERVABILITY (NEW in v5)               │
│                                                              │
│  Traces every LangChain call · Every LangGraph execution    │
│  Every RAG query · Latency · Token usage · Errors           │
│  Dashboard: smith.langchain.com                             │
└─────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                   REACT DASHBOARD (PWA)                      │
│         WebSocket push · Real-time PnL · Signal Radar        │
│    RAG Chat Widget · Agent Trace View · LangSmith Link       │
│         Multi-tier SaaS · Google OAuth · Mobile Ready        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🤖 RAG Intelligence Layer (New in v5)

The biggest addition in v5 is a full **Retrieval-Augmented Generation** pipeline that gives the AI assistant access to your actual trading history.

### How It Works

```
User asks: "Why do my signals fail on Fridays?"
                    │
                    ▼
         Embed question as vector
                    │
                    ▼
    Search ChromaDB across 5 collections
                    │
                    ▼
    Retrieve most relevant chunks:
    - Trade #47: Friday, Asia session, loss
    - Trade #52: Friday, low ADX, loss
    - Daily summary: Friday performance
                    │
                    ▼
    Send retrieved context to Groq LLM
                    │
                    ▼
    Answer grounded in YOUR actual data:
    "Your Friday signals show 31% WR vs
     61% overall. 8 of 11 losses occurred
     during Asia session with ADX below 20"
```

### 5 Chunk Types

| Chunk Type | Source | Good For |
|------------|--------|----------|
| Trade chunks | trades table | Loss analysis, pattern finding |
| Signal chunks | signals table | Signal quality questions |
| Daily summaries | trades grouped by day | Period performance |
| Coin performance | trades grouped by coin | Coin-specific analysis |
| Documentation | README + WORKING.md | Concept explanations |

### Tech Stack

```
Embeddings:   sentence-transformers/all-MiniLM-L6-v2
              Runs locally — zero cost — data stays on server
Vector Store: ChromaDB — persistent, local, no external deps
LLM:          Groq llama-3.3-70b — free tier, 0.5s response
Framework:    LangChain 0.3 — retrieval chains
Re-indexing:  Every 30 minutes via APScheduler
```

---

## 🕸️ LangGraph Signal Agent (New in v5)

The signal analysis pipeline was converted from linear Python code into a proper **LangGraph stateful agent graph**.

### The Graph

```
START
  ↓
[context_node]  — EMA direction + BTC alignment
  ↓ PASS / → [reject_node] → END
[sweep_node]    — Liquidity sweep detection
  ↓ PASS / → [reject_node] → END
[zone_node]     — Order block / FVG detection
  ↓ PASS / → [reject_node] → END
[trigger_node]  — 15M entry pattern confirmation
  ↓ PASS / → [reject_node] → END
[risk_node]     — SL/TP calculation + RR check
  ↓ PASS / → [reject_node] → END
[grade_node]    — 16-factor confluence scoring
  ↓ PASS / → [reject_node] → END
[ml_node]       — LightGBM win probability gate
  ↓ PASS / → [reject_node] → END
[finalize_node] — Sizing + narrative generation
  ↓
END
```

### Why This Matters

```
Before LangGraph:
  Linear Python if/else
  Black box — hard to debug
  No visibility into decisions
  Hard to explain to others

After LangGraph:
  Every step is a visible node
  Every decision is logged
  Full execution trace available
  Observable in LangSmith
  Easy to explain in interviews
  Can visualize the graph
```

---

## 🔭 LangSmith Observability (New in v5)

Every AI operation is traced through **LangSmith** — the official observability platform for LangChain and LangGraph.

```
What LangSmith traces:
  RAG queries:
    - Question asked
    - Documents retrieved
    - Similarity scores
    - LLM prompt sent
    - LLM response received
    - Total latency

  LangGraph executions:
    - Which nodes ran
    - Which edges were taken
    - Why signals were rejected
    - Full execution trace
    - Node-level timing

  LangChain calls:
    - Chain inputs and outputs
    - Token usage
    - Model used
    - Errors and retries
```

Dashboard: `https://smith.langchain.com`

Setup:
```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__your_key
LANGCHAIN_PROJECT=signal-engine-v5
```

---

## ⚡ How A Signal Is Born (v5 with LangGraph)

```
Every 15 minutes (:00 :15 :30 :45 UTC)
         │
         ▼
Fetch market data from Redis
         │
         ▼
LangGraph Agent starts
(traced in LangSmith)
         │
         ▼
[context_node]
  Check EMA direction + BTC alignment
  → NEUTRAL: reject with reason
  → LONG/SHORT: continue
         │
         ▼
[sweep_node]
  Detect liquidity sweep on 1H
  Score sweep quality
  → Below threshold: reject
  → Above threshold: continue
         │
         ▼
[zone_node]
  Find order block or FVG on 4H
  Score zone quality
  → Not found: reject
  → Found: continue
         │
         ▼
[trigger_node]
  Look for 15M entry pattern
  Engulfing or pin bar in zone
  → No pattern: reject
  → Pattern confirmed: continue
         │
         ▼
[risk_node]
  Calculate structure-aware SL
  Find nearest structure TP
  Check RR ratio
  → RR too low: reject
  → Valid: continue
         │
         ▼
[grade_node]
  Score 16 confluence factors
  Assign grade A+/A/B/F
  → Grade F: reject
  → Grade B+: continue
         │
         ▼
[ml_node]
  LightGBM win probability
  → Below 65%: reject
  → Above 65%: continue
         │
         ▼
[finalize_node]
  Calculate position size
  Generate narrative
  Write to Redis
         │
         ▼
Execute on Binance Futures
Send Telegram alert
Trigger content pipeline
Push to dashboard via WebSocket
Index new signal into RAG vector store
LangSmith records full trace
```

---

## 📊 Signal Grading System

| Grade | Score | Action | Risk | TP Multiplier |
|-------|-------|--------|------|---------------|
| 🏆 **A+** | 85-100 | Auto-execute | 2% capital | 2.5x risk |
| ✅ **A** | 68-84 | Auto-execute | 1.5% capital | 2.0x risk |
| 👀 **B** | 52-67 | Paper only | 1% capital | 1.5x risk |
| ⏳ **C** | 38-51 | Watch only | Never | — |
| 🚫 **F** | 0-37 | Hard blocked | Never | — |

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
| Scheduling | APScheduler | 15-min scan + RAG reindex jobs |
| Indicators | TA-Lib, Pandas, NumPy | Technical analysis |
| ML | LightGBM + scikit-learn | Signal win probability |
| RAG | LangChain + ChromaDB | Retrieval augmented generation |
| Embeddings | sentence-transformers | Local CPU embeddings |
| Agents | LangGraph | Stateful signal agent graph |
| Observability | LangSmith | AI tracing + monitoring |
| Alerts | Telegram Bot API + HTTPX | Real-time notifications |
| Content | Groq llama-3.3-70b | AI post + RAG answers |
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
│   ├── scheduler.py         # APScheduler · scan · ML · RAG reindex
│   ├── chatbot_rag.py       # RAG-powered chatbot entry point
│   │
│   ├── 📂 rag/              # ⭐ RAG Intelligence Layer (NEW)
│   │   ├── vectorstore.py   # ChromaDB setup + collection management
│   │   ├── indexer.py       # 5 chunk types · trade/signal indexing
│   │   ├── retriever.py     # Semantic search · intent detection
│   │   └── chain.py         # LangChain RAG chain · Groq integration
│   │
│   ├── 📂 agents/           # ⭐ LangGraph Agent Pipeline (NEW)
│   │   ├── state.py         # SignalAgentState TypedDict
│   │   ├── graph.py         # LangGraph graph definition
│   │   ├── signal_agent.py  # Agent entry point
│   │   └── nodes/
│   │       ├── context_node.py   # EMA + BTC alignment
│   │       ├── sweep_node.py     # Liquidity sweep detection
│   │       ├── zone_node.py      # Order block / FVG
│   │       ├── trigger_node.py   # 15M entry pattern
│   │       ├── risk_node.py      # SL/TP calculation
│   │       ├── grade_node.py     # Confluence scoring
│   │       └── ml_node.py        # LightGBM gate
│   │
│   ├── 📂 monitoring/       # ⭐ LangSmith Observability (NEW)
│   │   └── langsmith_setup.py   # LangSmith tracing setup
│   │
│   ├── 📂 engines/          # Core intelligence (unchanged)
│   │   ├── indicators.py    # EMA · RSI · MACD · ATR · ADX
│   │   ├── signal.py        # Original signal pipeline (fallback)
│   │   ├── sweep.py         # Liquidity sweep detection
│   │   ├── zone.py          # Order block / FVG detection
│   │   ├── trigger.py       # Entry pattern detection
│   │   ├── risk.py          # SL/TP calculation
│   │   ├── scorer.py        # Grade assignment
│   │   └── PROPRIETARY.md
│   │
│   ├── 📂 ml/               # ML pipeline (unchanged)
│   │   └── PROPRIETARY.md
│   │
│   ├── 📂 alerts/           # Telegram + scanner
│   ├── 📂 trade/            # Execution + monitoring
│   ├── 📂 data/             # Fetcher + store + cache
│   ├── 📂 api/              # REST endpoints
│   ├── 📂 backtest/         # Backtest engine
│   └── 📂 content/          # Content pipeline
│
└── 📂 frontend/
    └── 📂 src/
        ├── 📂 pages/        # 11 dashboard pages
        └── 📂 components/   # UI components
```

---

## 🌐 API Reference

### New RAG + Agent Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | RAG-powered chat with trade history |
| `GET` | `/api/rag/status` | Vector store health + chunk counts |
| `POST` | `/api/rag/reindex` | Force full reindex of all data |
| `GET` | `/api/langsmith/status` | LangSmith tracing status |

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
| `GET` | `/api/health` | System health + RAG + LangSmith |
| `WS` | `/ws/dashboard` | Real-time push every 2s |

---

## 🔒 Security

- **Google OAuth** — Secure user authentication
- **TOTP (2FA)** — Required for mode switching and dangerous actions
- **JWT Sessions** — Secure session management with device tracking
- **Rate Limiting** — All endpoints protected via slowapi
- **API Keys** — Programmatic access with prefix tracking
- **Audit Log** — Every action logged with IP and timestamp

---

## ⏱️ Scan + Reindex Schedule

| Job | Schedule | Description |
|-----|----------|-------------|
| Coin scan | `:00/:15/:30/:45 UTC` | Full universe analysis |
| RAG reindex | `Every 30 min` | Index new trades + signals |
| Morning briefing | `08:00 UTC` | London open summary |
| Evening briefing | `14:30 UTC` | NY open summary |
| Outcome sync | `Every 30 min` | Closed trade sync |
| ML check | `Every 1 hour` | Auto-train trigger |

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
│ RAG ❌   │ RAG ❌   │ RAG ✅   │ RAG ✅   │
│ API ❌   │ API ❌   │ API ✅   │ API ✅   │
│ 5 coins  │All coins │All coins │All coins │
└──────────┴──────────┴──────────┴──────────┘
```

---

## 🖥️ Infrastructure

```
AWS EC2 t3.small (2 vCPU · 2GB RAM)
│
├── Nginx (system service)
│   └── signal-engine-v5.vishalkool.top → :8000
│
└── Docker Compose
    ├── redis:7-alpine          (~10MB RAM)
    └── signal-engine           (~900MB RAM)
        ├── FastAPI backend
        ├── React frontend (served as static)
        ├── LangGraph agent pipeline
        ├── RAG vector store (ChromaDB)
        ├── sentence-transformers (local CPU)
        ├── LangSmith tracing (cloud)
        └── All background jobs
```

---

## 🔒 Proprietary Components

| File | Contains |
|------|----------|
| `engines/confluence.py` | 16-factor weighted scoring engine |
| `engines/signal.py` | Signal generation + grading logic |
| `engines/sweep.py` | Liquidity sweep detection algorithm |
| `engines/zone.py` | Order block / FVG detection |
| `engines/trigger.py` | 15M entry pattern detection |
| `engines/risk.py` | Structure-aware SL/TP calculation |
| `agents/graph.py` | LangGraph signal agent graph |
| `rag/chain.py` | LangChain RAG pipeline |
| `rag/indexer.py` | 5-type chunking strategy |
| `ml/trainer.py` | LightGBM training pipeline |
| `ml/predictor.py` | Win probability prediction |
| `alerts/scanner.py` | Core scan orchestration |
| `content/pipeline.py` | AI content generation pipeline |

📧 **Contact for full review:** vishalkool166@gmail.com

---

## 🚀 Built With Prompt Engineering + AI Augmented Development

This entire system — 50+ Python files, 70+ React components, RAG pipeline, LangGraph agents, full infrastructure — was **architected and built through structured prompt engineering** over 2 months.

No traditional software engineering background.
100% production deployed and running live.

**v5 specifically demonstrates:**
- Designing and implementing RAG pipelines from scratch
- Converting existing logic into LangGraph agent graphs
- Integrating LangSmith observability into production AI systems
- Making architectural decisions about embeddings, chunking, and retrieval
- Deploying AI systems to production with zero downtime

---

## 📞 Contact

<div align="center">

**Vishal Katike**

[![Email](https://img.shields.io/badge/Email-vishalkool166@gmail.com-D14836?style=for-the-badge&logo=gmail&logoColor=white)](mailto:vishalkool166@gmail.com)
[![Phone](https://img.shields.io/badge/Phone-+91_8978439995-25D366?style=for-the-badge&logo=whatsapp&logoColor=white)](tel:+918978439995)
[![Location](https://img.shields.io/badge/Location-Hyderabad,_India-FF9900?style=for-the-badge&logo=googlemaps&logoColor=white)](https://maps.google.com/?q=Hyderabad)

*Open to: AI Engineer · RAG Engineer · LangChain Developer · AI Product Engineer · Prompt Engineer · AI Solutions Engineer*

</div>

---

<div align="center">

*Built with Python · FastAPI · Redis · LightGBM · LangChain · LangGraph · LangSmith · ChromaDB · React · TypeScript*

⭐ Star this repo if you found it interesting!

</div>