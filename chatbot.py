import logging
from groq import AsyncGroq
from config import cfg

log = logging.getLogger(__name__)

_client = AsyncGroq(api_key=cfg.GROQ_API_KEY) if cfg.GROQ_API_KEY else None

_APP_KEYWORDS = {
    "trade", "signal", "grade", "long", "short", "sl", "stop", "tp1", "tp2",
    "btc", "eth", "coin", "scan", "regime", "sweep", "displacement", "retest",
    "confluence", "score", "health", "pnl", "profit", "loss", "risk", "capital",
    "leverage", "funding", "oi", "fear", "greed", "session", "rsi", "macd",
    "atr", "adx", "ema", "bot", "engine", "signal", "backtest", "factor",
    "drawdown", "margin", "position", "order", "block", "fvg", "bos", "choch",
    "daily", "cap", "paper", "live", "win", "rate", "streak", "briefing",
    "why", "what", "how", "when", "explain", "status", "active", "idle",
    "invalidated", "warning", "healthy", "thesis", "entry", "exit", "close",
    "open", "paused", "resume", "mode", "queue", "approve", "skip",
}

_SYSTEM_PROMPT = """You are a trading teacher assistant for Signal Engine v5, an automated crypto futures trading bot.

STRICT RULES:
- ONLY answer questions about Signal Engine v5 and its trading concepts
- Refuse ALL off-topic questions politely with: "I only answer questions about your Signal Engine trading app."
- Explain everything in plain simple English for a complete beginner
- Use analogies where helpful
- Keep answers short (3-5 sentences) unless more detail is explicitly asked
- Never use jargon without explaining it immediately after
- Always refer to the live app data provided when answering about current state

KEY CONCEPTS YOU KNOW:
- LONG = betting price goes up. SHORT = betting price goes down.
- SL (Stop Loss) = the price where the bot exits to limit your loss
- TP1/TP2 = Take Profit levels — where the bot locks in gains
- Grade A+/A = strong signal, B = watching, C = building, F = blocked
- Confluence Score /100 = how many conditions align for a trade
- Regime = overall market condition (trending, ranging, choppy)
- Sweep = smart money hunting stop losses before the real move
- Displacement = a strong fast candle showing institutional intent
- Retest = price returning to the swept zone to confirm direction
- ATR = Average True Range — measures how much price moves normally
- RSI = momentum indicator — above 70 = overbought, below 30 = oversold
- Funding Rate = cost of holding a futures position — extreme = squeeze risk
- OI = Open Interest — total open contracts — rising OI confirms trend
- BTC Alignment = whether Bitcoin's trend matches the coin being traded
- Session = London/NY overlap is best for trading, Asia is low quality
- Paper Trading = simulated trading with fake money to test the system
- PnL = Profit and Loss
- Leverage = multiplier on position size — 10x means $10 controls $100
- Drawdown = how much the account dropped from its peak
- Health State = HEALTHY (thesis intact), WARNING (weakening), INVALIDATED (exit signal)
- Daily Cap = maximum loss allowed per day before bot stops trading
- Order Block = price zone where institutions placed large orders
- FVG = Fair Value Gap — imbalance in price that often gets filled
- BOS = Break of Structure — confirms trend direction
- CHoCH = Change of Character — early reversal signal"""


def is_app_related(message: str) -> bool:
    lower = message.lower()
    return any(kw in lower for kw in _APP_KEYWORDS)


async def get_live_context() -> str:
    lines = []

    try:
        from trade.state import state_manager
        from trade.risk import risk_guard
        from data.cache import cache
        from alerts.scanner import get_db_stats
        from config import cfg

        # Bot config
        lines.append(f"=== BOT CONFIG ===")
        lines.append(f"Mode: {'PAPER' if cfg.PAPER_TRADING else 'LIVE'}")
        lines.append(f"Capital: ${cfg.CAPITAL}")
        lines.append(f"Leverage: {cfg.LEVERAGE}x")
        lines.append(f"Min grade to trade: {', '.join(cfg.MIN_GRADE_TO_TRADE)}")
        lines.append(f"Max trades/day: {cfg.MAX_TRADES_PER_DAY}")
        lines.append(f"Daily loss cap: {cfg.DAILY_LOSS_CAP_PCT * 100:.0f}% (${cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT:.2f})")
        lines.append(f"Coins watched: {', '.join(cfg.COINS)}")

        # Trade state
        lines.append(f"\n=== CURRENT TRADE ===")
        if state_manager.is_idle:
            lines.append("State: IDLE — no active trade")
            lines.append(f"Auto-execution: {'PAUSED' if state_manager.is_paused else 'ACTIVE'}")
        else:
            t = state_manager.current_trade
            lines.append(f"State: IN TRADE")
            lines.append(f"Coin: {t.coin}USDT {t.direction}")
            lines.append(f"Grade: {t.grade}")
            lines.append(f"Entry: {t.entry_price}")
            lines.append(f"Stop Loss: {t.sl_price}")
            lines.append(f"TP1: {t.tp1_price}")
            lines.append(f"TP2: {t.tp2_price}")
            lines.append(f"Position size: ${t.position_size:.2f}")
            lines.append(f"Risk amount: ${t.risk_amt:.4f}")
            lines.append(f"TP1 hit: {state_manager.is_tp1_hit}")
            lines.append(f"Health: {state_manager.health_state}")

            hd = state_manager.health_data
            if hd.get("failures"):
                lines.append(f"Health failures: {'; '.join(hd['failures'][:3])}")
            if hd.get("warnings"):
                lines.append(f"Health warnings: {'; '.join(hd['warnings'][:3])}")
            if hd.get("checks"):
                lines.append(f"Health checks OK: {'; '.join(hd['checks'][:3])}")

        # Daily risk
        lines.append(f"\n=== DAILY RISK ===")
        risk = risk_guard.get_daily_stats()
        lines.append(f"Trades taken today: {risk['trades_taken']}/{cfg.MAX_TRADES_PER_DAY}")
        lines.append(f"Trades remaining: {risk['remaining_trades']}")
        lines.append(f"PnL today: ${risk['total_pnl']:.4f}")
        lines.append(f"Loss today: ${abs(risk['total_loss']):.4f}")
        lines.append(f"Loss cap remaining: ${risk['remaining_loss']:.4f}")
        lines.append(f"Cap hit: {risk['cap_hit']}")

        # Signal cache — all coins
        lines.append(f"\n=== CURRENT SIGNALS ===")
        for coin in cfg.COINS:
            cached = cache.get_raw(f"signal_{coin}")
            if not cached:
                continue
            grade  = cached.get("grade", "F")
            dir_   = cached.get("direction", "--")
            score  = cached.get("score", 0)
            regime = cached.get("regime", "--")
            sess   = cached.get("session", "--")
            expl   = cached.get("explanation", {})
            conf   = expl.get("confidence_label", "")
            no_trade = cached.get("no_trade", {}) or {}
            hards  = no_trade.get("hard_blocks", [])
            softs  = no_trade.get("soft_blocks", [])

            line = f"{coin}: Grade {grade} | {dir_} | Score {score}/100 | {regime} | {sess}"
            if conf:
                line += f" | Confidence: {conf}"
            lines.append(line)

            if expl.get("thesis"):
                lines.append(f"  Thesis: {expl['thesis'][:200]}")
            if expl.get("no_trade_reason"):
                lines.append(f"  No-trade reason: {expl['no_trade_reason'][:200]}")
            if hards:
                lines.append(f"  Hard blocks: {'; '.join(b['reason'] for b in hards[:2])}")
            if softs:
                lines.append(f"  Soft blocks: {'; '.join(b['reason'] for b in softs[:2])}")

        # All-time stats
        lines.append(f"\n=== ALL TIME STATS ===")
        try:
            stats = get_db_stats()
            if stats:
                lines.append(f"Total closed trades: {stats.get('closed', 0)}")
                lines.append(f"Win rate: {stats.get('win_rate', 0)}%")
                lines.append(f"Total PnL: ${stats.get('total_pnl', 0)}")
                bg = stats.get("by_grade", {})
                for g in ["A+", "A"]:
                    gd = bg.get(g, {})
                    if gd.get("total", 0) > 0:
                        lines.append(
                            f"Grade {g}: {gd['total']} trades | "
                            f"{gd['win_rate']}% WR | ${gd['total_pnl']} PnL"
                        )
        except Exception:
            pass

    except Exception as e:
        log.error(f"get_live_context error: {e}")
        lines.append("(Live context partially unavailable)")

    return "\n".join(lines)


async def chat(user_message: str) -> str:
    if not _client:
        return "AI chatbot not configured. Add GROQ_API_KEY to .env and restart."

    if not is_app_related(user_message):
        return "I only answer questions about your Signal Engine trading app."

    try:
        context = await get_live_context()

        messages = [
            {
                "role": "system",
                "content": _SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": (
                    f"LIVE APP DATA:\n{context}\n\n"
                    f"USER QUESTION: {user_message}"
                )
            }
        ]

        response = await _client.chat.completions.create(
            model       = "llama-3.3-70b-versatile",
            messages    = messages,
            max_tokens  = 400,
            temperature = 0.4,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        log.error(f"Groq chat error: {e}")
        return "AI is temporarily unavailable. Try /help for commands."