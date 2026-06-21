import logging
from groq import AsyncGroq
from config import cfg

log = logging.getLogger(__name__)

_client = AsyncGroq(api_key=cfg.GROQ_API_KEY) if cfg.GROQ_API_KEY else None

_SYSTEM_PROMPT = """You are a trading assistant for Signal Engine v5, an automated crypto futures trading bot.

STRICT RULES:
- ONLY answer questions about Signal Engine v5, its trades, signals, and trading concepts related to this app
- Refuse ALL off-topic questions politely with: "I only answer questions about your Signal Engine trading app."
- ALWAYS check live app data first before answering
- ALWAYS mention actual values (prices, grades, scores, reasons) from live data
- THEN explain what those values mean in simple terms
- Never give generic explanations when live data is available
- Example: Don't say "invalidated means conditions changed"
  Say "Your BTCUSDT LONG is invalidated because: [actual reason from health failures data]"
- Explain everything in plain simple English for a complete beginner
- Use analogies where helpful
- Keep answers short (3-5 sentences) unless more detail is explicitly asked
- Never use jargon without explaining it immediately after
- If live data is not available for a specific question, say so clearly

KEY CONCEPTS YOU KNOW:
- LONG = betting price goes up. SHORT = betting price goes down.
- SL (Stop Loss) = the price where the bot exits to limit your loss
- TP1/TP2 = Take Profit levels — where the bot locks in gains
- Grade A+/A = strong signal, B = skipped, C = building, F = blocked
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
- Daily Cap = maximum loss allowed per day before bot stops trading
- Order Block = price zone where institutions placed large orders
- FVG = Fair Value Gap — imbalance in price that often gets filled
- BOS = Break of Structure — confirms trend direction
- CHoCH = Change of Character — early reversal signal"""


def _detect_intent(message: str) -> str:
    m = message.lower()
    if any(w in m for w in ["coin", "btc", "eth", "signal", "grade", "score", "regime", "session"]):
        return "signal"
    return "general"


async def _get_context_for_intent(intent: str) -> str:
    lines = []
    try:
        from data.cache import cache
        from config import cfg

        lines.append(f"Capital: ${cfg.CAPITAL:.2f}")

        if intent in ("signal", "general"):
            has_signals = False
            for coin in cfg.COINS[:8]:
                cached = cache.get_raw(f"signal_{coin}")
                if not cached:
                    continue
                has_signals = True
                grade  = cached.get("grade", "F")
                dir_   = cached.get("direction", "--")
                score  = cached.get("score", 0)
                lines.append(f"{coin}: Grade {grade} | {dir_} | Score {score}/100")
            if not has_signals:
                lines.append("No signal cache — run /scan")

        from alerts.scanner import get_db_stats
        stats = get_db_stats()
        if stats:
            lines.append(f"All-time: {stats.get('closed',0)} trades | WR:{stats.get('win_rate',0)}% | PnL:${stats.get('total_pnl',0)}")

    except Exception as e:
        log.error(f"Context error: {e}")
        lines.append("(Live context partially unavailable)")

    return "\n".join(lines)


async def chat(user_message: str) -> str:
    if not _client:
        return "AI chatbot not configured. Add GROQ_API_KEY to .env and restart."

    try:
        intent  = _detect_intent(user_message)
        context = await _get_context_for_intent(intent)

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"LIVE APP DATA:\n{context}\n\nUSER QUESTION: {user_message}"
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