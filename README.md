Signal Engine v5

«Status: Experimental / under active development. This repository is shared for independent technical review. It is not a verified profitable strategy or a production-ready trading product.»

Signal Engine v5 is a Python/FastAPI trading-intelligence application with crypto-futures and Indian-equity strategy modules, risk-management components, scheduled scanning, alerts, a dashboard, and AI/RAG integrations.

- Repository: https://github.com/vishalkool166/crypto-engine
- Live demo: https://signal-engine-v5.vishalkool.top
- Developer: Vishal Katike

---

⚠️ Read This First

- No verified trading edge is claimed. Any live-trading figures below are preliminary observations from a very small sample and have not been independently audited.
- Do not use real funds to evaluate this project. Start with code review, tests, paper trading, or an exchange testnet. Automated trading can lose money quickly.
- AI-assisted development: AI coding tools were used extensively during development. Strategy assumptions, implementation, backtesting, and security still need independent review.
- Deployment is not proof of correctness. A running application does not necessarily mean that its strategies are profitable, its calculations are correct, or its security is adequate.
- Security caution: The current "docker-compose.yml" mounts the host Docker socket into the application container. This can grant substantial host-level control if the container is compromised. Review and remove this mount unless it is essential before running the project.
- Licensing: No root-level "LICENSE" file is currently present. A public repository does not automatically grant unrestricted permission to reuse or redistribute its code.
- Protect credentials: Never commit exchange API keys, OAuth secrets, Telegram tokens, or other credentials to source control.

What Feedback Would Help Most?

1. Backtesting correctness: exits, breakeven outcomes, fees, funding, slippage, and timeouts.
2. Consistency between backtest signals and the live signal-generation path.
3. Stop-loss, take-profit, position sizing, leverage, and circuit-breaker behavior.
4. Security, deployment configuration, and secret handling.
5. Tests and reproducible steps for running the core components.

---

🧠 What Is This?

Signal Engine v5 is a trading-intelligence application containing crypto-futures and Indian-equity strategy modules, risk-management components, scheduled scanning, alerts, a web dashboard, and AI/RAG integrations.

The repository includes code paths for automated execution. Reviewers should not connect live trading credentials or enable live execution while evaluating the project.

Crypto Futures — Binance

The project includes a Binance Futures workflow intended to:

- Scan a configured cryptocurrency universe on a schedule.
- Evaluate technical indicators and market conditions across timeframes.
- Score signals using trend strength, momentum, and volume.
- Apply risk calculations and position-sizing logic.
- Integrate with an agent pipeline, alerts, and execution components.

Indian Markets — AngelOne

The project includes an Indian-market workflow using AngelOne SmartAPI, with an Opening Range Breakout (ORB) strategy for BANKNIFTY and FINNIFTY.

The documented approach monitors the opening range and evaluates potential breakdown conditions during configured entry windows.

Dashboard and Supporting Components

The repository also contains:

- A FastAPI application with REST and WebSocket endpoints.
- Dashboard build assets under "frontend/".
- Redis-backed caching and state components.
- SQLite and SQLAlchemy persistence.
- Scheduled jobs and Telegram alerts.
- Backtesting and reporting modules.
- Risk calculation, signal scoring, trend/regime detection, and position sizing.
- LangGraph agent, RAG/ChromaDB, and LangSmith integration code.
- Authentication, session, and SaaS-tier code.

Frontend limitation: The repository currently contains built/static frontend assets, but the editable React/TypeScript source and a frontend package manifest are not present. The frontend therefore cannot be assumed to be reproducible from source using this repository alone.

---

🏗️ Architecture Overview

Market Data / Exchange APIs
             |
             v
Data Fetching, Cache, and Persistence
             |
             v
Indicators -> Regime/Trend Checks -> Signal Scoring
             |
             v
Risk Calculation and Position Sizing
             |
             v
Strategy Decisions / Agent Workflow
             |
             +----> Backtesting and Reporting
             |
             +----> Dashboard API / WebSocket
             |
             +----> Telegram Alerts
             |
             +----> Exchange Execution Code
             |
             v
Optional AI/RAG and Observability Integrations

This is a high-level view of the intended components, not a guarantee that every path is fully tested or consistent. In particular, backtest/live-strategy parity needs independent verification.

---

📊 Signal Scoring

The current scoring description uses three main factors.

Factor| Purpose
ADX| Assess trend strength
RSI| Assess momentum context
Volume| Check for volume expansion or confirmation

Scores and grades are heuristics. Their thresholds should be treated as hypotheses to test, not as evidence of predictive power.

Grade Thresholds

The existing project documentation describes the following grades:

Grade| Score| Documented Action
A+| 80–100| Auto-execution configured
A| 65–79| Auto-execution configured
B| 50–64| Removed from trading according to project notes
F| 0–49| Blocked

These are documented configurations, not independently validated recommendations. Review the actual implementation before assuming the thresholds or actions match this table.

Preliminary Live Observations — Not Validated Performance

The project's earlier notes recorded this small-sample snapshot:

Grade| Trades| Reported Win Rate| Reported P&L
A| 6| 50%| +$53.19
B| 15| 13%| -$122.16 (subsequently disabled)

Important limitations:

- These figures are not independently audited.
- The README does not establish a complete observation period or provide enough methodology to assess execution quality.
- The full treatment of fees, funding, slippage, and other trading costs needs verification.
- Six trades are far too few to establish a reliable trading edge.
- The reported results should not be used to forecast returns or make financial decisions.

The purpose of sharing these figures is transparency, not to claim profitability.

---

🕸️ LangGraph Agent Pipeline

The repository includes a LangGraph-based signal-agent workflow.

The documented pipeline consists of nodes for:

1. Market-regime assessment.
2. Trend-direction checks.
3. Risk calculations.
4. Signal grading.
5. Position sizing.
6. Final signal construction.

The intended design is to make decisions and rejection reasons easier to inspect.

However, the relationship between this pipeline, the underlying strategy modules, and the backtesting implementation needs independent review. The existence of a pipeline does not guarantee that its decisions are correct or profitable.

---

🇮🇳 Indian Markets — ORB Strategy

The Indian-market module implements an Opening Range Breakout approach for BANKNIFTY and FINNIFTY using AngelOne SmartAPI.

The existing project notes describe:

- An opening range formed after the market opens.
- Configurable range-size and prior-session filters.
- A defined entry window.
- Potential short entries following a breakdown.
- Stop-loss, target, and time-based exit rules.

Strategy Hypothesis

The current approach explores whether morning breakdowns under selected market conditions can produce follow-through.

This is a hypothesis to test, not an established statistical edge. It requires realistic costs, out-of-sample testing, and independent validation before being considered suitable for live trading.

---

🤖 RAG Intelligence Layer

The repository contains a Retrieval-Augmented Generation pipeline intended to make trading-related data and documentation accessible to an AI assistant.

The documented components include:

- ChromaDB vector storage.
- Sentence-transformers embeddings.
- LangChain retrieval components.
- Groq LLM integration.
- Indexing and retrieval modules for trading-related information.

The intended use cases include asking questions about trading history, signal behavior, and project documentation.

The accuracy of answers depends on the quality of the retrieved data, the indexing process, and the model's responses. AI-generated explanations should not be treated as proof of strategy performance.

---

🔭 LangSmith Observability

The repository includes LangSmith integration code for observing AI-related operations.

Depending on configuration, tracing can help developers investigate:

- Agent workflow execution.
- Retrieval behavior.
- Latency and errors.
- LLM inputs and outputs.

Reviewers should verify which operations are traced and whether sensitive information could be captured before enabling tracing with real account data.

---

⏱️ Scheduled Jobs

The existing documentation describes scheduled activities including:

Job| Documented Purpose
Crypto scanning| Periodic cryptocurrency analysis
RAG indexing| Refreshing indexed trading information
Briefings| Generating market summaries
Outcome synchronization| Updating closed-trade information
ML checks| Checking model-training conditions
Indian-market scanning| Evaluating configured ORB conditions
Market close| Handling configured end-of-session activities

Actual schedules, timezone handling, and behavior should be verified against "scheduler.py" and the related implementation before relying on these jobs.

---

🛠️ Technology Stack

Area| Technologies Used in the Repository
Runtime and API| Python 3.11+, FastAPI, Uvicorn
Market data and execution| CCXT/Binance Futures, AngelOne SmartAPI
Data and scheduling| Redis, SQLite, SQLAlchemy, APScheduler
Analysis| Pandas, NumPy, technical-analysis libraries
Strategy workflow| Python strategy modules, LangGraph
ML and outcome tracking| LightGBM-related components and tracking modules
RAG| LangChain, ChromaDB, sentence-transformers, Groq integration
Observability| LangSmith integration
Frontend| Committed static/build assets under "frontend/"
Deployment| Docker, Docker Compose, Nginx configuration

The presence of a dependency or integration in the repository does not mean it is required for every workflow or fully configured for a fresh installation.

---

🏢 SaaS and Authentication Components

The repository includes SaaS-related code for authentication, sessions, user tiers, and administrative functionality.

These components are part of the current implementation, but their presence should not be interpreted as a security certification or a claim that the application is ready to serve paying customers.

Before using this as a public service, the authentication flows, authorization boundaries, session management, rate limiting, data isolation, payment handling (if added), and operational security need dedicated testing and review.

---

🔒 Security Considerations

The codebase includes security-related components such as authentication, TOTP, sessions, rate limiting, and audit-related functionality.

These features still need independent verification. In particular:

- Review the Docker socket mount in "docker-compose.yml".
- Keep credentials out of source control and logs.
- Use least-privilege exchange API keys.
- Disable withdrawals on exchange keys wherever supported.
- Do not expose administrative or trading endpoints publicly without reviewing authentication and authorization.
- Verify how the application behaves when Redis or other dependencies are unavailable.
- Review what data is sent to external AI and observability services.
- Use an isolated environment for evaluation.

Do not assume that the presence of a security feature means the application is secure.

---

📁 Project Structure

The following paths reflect the current repository layout. Some generated frontend assets are committed, but the editable frontend source is not currently included.

crypto-engine/
├── main.py                 # FastAPI application
├── config.py               # Configuration
├── requirements.txt        # Python dependencies
├── Dockerfile
├── docker-compose.yml
├── agents/                 # Signal-agent pipeline and nodes
├── api/                    # API routes and dashboard endpoints
├── alerts/                 # Scanner, briefings, Telegram alerts
├── backtest/               # Backtest engine and reporting
├── data/                   # Data fetching, caching, storage
├── engines/
│   ├── crypto/             # Crypto strategy
│   ├── indian/             # Indian-market strategy modules
│   ├── core/               # Indicators, candles, regime
│   ├── risk/               # Risk calculations
│   ├── scoring/             # Signal scoring
│   ├── sizing/              # Position sizing
│   └── trend/               # Trend direction
├── ml/                     # Model and outcome-tracking code
├── monitoring/             # LangSmith setup
├── rag/                    # Retrieval-augmented generation
├── saas/                   # Authentication, tiers, sessions
├── trade/                  # Exchange integration and execution
└── frontend/
    ├── index.html
    └── assets/             # Built/static frontend assets

---

🚀 Running and Configuration

The repository includes a "Dockerfile", "docker-compose.yml", and "requirements.txt". However, this README does not yet provide a fresh-clone setup that has been verified to work safely without live credentials.

I do not want to provide untested commands or imply that a safe paper-trading mode is available if it has not been verified.

Before attempting to run the project:

1. Review "config.py" and the code paths that read environment variables to identify required configuration.
2. Do not populate live exchange credentials merely to inspect the code.
3. Review "docker-compose.yml", particularly the Docker socket mount and exposed ports.
4. Identify which scheduled jobs can place orders and verify how live execution can be disabled.
5. Use an isolated environment and an exchange testnet or paper-trading mode only where the code explicitly supports it.
6. Check that logs and error responses do not expose credentials or account information.

Contributions that add a minimal, reproducible, safe reviewer setup and automated tests would be especially valuable.

---

🌐 API Endpoints

The application includes API routes for areas such as dashboard data, chat/RAG, Indian-market status, backtesting, health checks, and WebSocket updates.

For authoritative route details and authentication requirements, inspect "main.py" and the routers under "api/". Exact availability may change as the project evolves. Do not assume every route is publicly accessible or that every endpoint has been independently tested.

---

🧪 Help Wanted: Independent Technical Review

I'm particularly interested in actionable, reproducible feedback on the following areas.

1. Backtesting correctness

- Are trade outcomes calculated correctly?
- Are breakeven exits distinguished from wins?
- Are fees, funding, and slippage represented appropriately?
- Are timed-out or unresolved trades handled consistently?
- How are candles handled when both stop-loss and take-profit levels could have been reached?

2. Strategy consistency

- Does the backtester faithfully represent the live signal-generation logic?
- Are indicators calculated consistently in both paths?
- Are entry and exit assumptions documented and reproducible?

3. Risk management

- Are position sizes and leverage handled safely?
- Are stop-loss and take-profit calculations correct?
- Do circuit breakers behave as intended during failures or fast market moves?

4. Security

- Are exchange integrations, authentication, secrets, and deployment defaults safe?
- Are permissions enforced consistently?
- What should be changed before a public deployment?

5. Testing and reproducibility

- Which unit and integration tests should be added first?
- What edge cases are currently missing?
- What is the smallest safe setup that would let a new contributor run a core component?

When reporting a bug, please include the relevant file/function, steps to reproduce, expected behavior, and actual behavior.

Constructive criticism is welcome. I'm especially interested in specific bugs and actionable suggestions rather than claims about whether the strategy will make money.

---

🤖 AI-Assisted Development

AI coding tools, including Claude, were used extensively during development alongside my own product and implementation decisions.

I'm sharing the project transparently and welcome review of both the code and the assumptions behind it. AI assistance is not a substitute for tests, independent review, or validation of trading performance.

---

📞 Contact

Vishal Katike

- Email: vishalkool166@gmail.com
- Repository: https://github.com/vishalkool166/crypto-engine
- Live demo: https://signal-engine-v5.vishalkool.top

---

This repository is for software development and research. It is not financial advice. Nothing here is a recommendation to buy or sell any asset. Automated trading involves substantial risk, including the loss of all funds allocated to it.
