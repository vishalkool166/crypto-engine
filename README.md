# Signal Engine v5 — Python Backend

## Setup

### 1. Install dependencies
pip install -r requirements.txt

### 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

### 3. Get API keys
- Binance: https://www.binance.com/en/my/settings/api-management
- Telegram Bot: message @BotFather on Telegram
- Finnhub: https://finnhub.io (free tier)

### 4. Run
python main.py

### 5. Open browser
http://localhost:8000

## Folder Structure
signal-engine/
├── main.py
├── config.py
├── scheduler.py
├── requirements.txt
├── .env
├── data/
│   ├── fetcher.py
│   └── cache.py
├── database/
│   └── signals.db (auto created)
├── engines/
│   ├── indicators.py
│   ├── regime.py
│   ├── sweep.py
│   ├── displacement.py
│   ├── retest.py
│   ├── confluence.py
│   └── signal.py
├── alerts/
│   ├── telegram.py
│   └── scanner.py
├── api/
│   └── routes.py
└── frontend/
    └── index.html