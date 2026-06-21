import json
import logging
import time
from database import SessionLocal, Signal as SignalModel

log = logging.getLogger(__name__)

_SIGNAL_PROMPT = """You are a crypto trading analyst writing for Twitter/X for Signal Engine v5.

RULES:
- Maximum 280 characters for twitter_draft
- Be specific — use actual prices, grades, scores from the signal
- No financial advice disclaimers in the post
- No "I" statements
- Include coin, direction, key level, and why it matters
- End with 2-3 relevant hashtags
- long_draft is 500-800 characters with full thesis and key levels

TONE INSTRUCTIONS:
- professional: factual, data-driven, concise, hedge fund analyst voice
- educational: explain the setup for beginners, use simple analogies, teach while informing
- humor: witty, slightly sarcastic, crypto twitter native voice, punchy one-liners, still includes real data. Examples: "BTC just hunted every stop below $60k and now wants to moon. Classic. Entry 61200 SL 59800. #Bitcoin" or "Smart money swept the lows, grabbed liquidity, now acting surprised it bounced. Entry confirmed. #Crypto"

OUTPUT FORMAT (JSON only, no other text):
{
  "twitter_draft": "...",
  "long_draft": "...",
  "hashtags": ["#BTC", "#CryptoTrading"],
  "tone_used": "professional"
}"""


_COMMENTARY_PROMPT = """You are a witty crypto market commentator writing for Twitter/X for Signal Engine v5.

RULES:
- Maximum 280 characters for twitter_draft
- Write about what the MARKET IS DOING right now — not trade signals
- No entry/SL/TP levels — this is commentary not a signal
- Be conversational, observational, sometimes educational
- Reference actual market data provided (regime, funding, fear/greed, session)
- End with 1-2 relevant hashtags
- long_draft is 300-500 characters expanding on the observation

TONE INSTRUCTIONS:
- humor: dry wit, sarcastic observation, crypto meme energy, relatable to traders
  Examples:
  "Market regime: choppy. ADX: 12. Translation: nobody knows anything right now. #Crypto"
  "Funding at 0.09%. Someone out there is very confident. History suggests otherwise. #Bitcoin"
  "It's Sunday. Liquidity left the building. Stop hunts incoming. You have been warned. #CryptoTrading"
  "Fear & Greed at 18. Last time it was this low, people were calling $10k BTC. Just saying. #Crypto"
  "London session opened. Market immediately did nothing. Respect the process. #CryptoTrading"
- educational: explain what the current condition means for traders in simple terms, use analogies
- professional: factual market state observation, what it means technically

OUTPUT FORMAT (JSON only, no other text):
{
  "twitter_draft": "...",
  "long_draft": "...",
  "hashtags": ["#Crypto", "#CryptoTrading"],
  "tone_used": "humor",
  "post_type": "commentary"
}"""


_SIGNAL_TONES = [
    "professional", "professional", "professional",
    "professional", "professional", "professional",
    "professional", "educational", "educational",
    "humor"
]

_COMMENTARY_TONES = [
    "humor", "humor", "humor", "humor",
    "educational", "educational",
    "professional", "professional",
    "humor", "humor"
]


async def generate_post_draft(signal_id: int) -> dict | None:
    try:
        from config import cfg
        from groq import AsyncGroq

        if not cfg.GROQ_API_KEY:
            log.error("GROQ_API_KEY not configured")
            return None

        with SessionLocal() as db:
            signal = db.query(SignalModel).filter(
                SignalModel.id == signal_id
            ).first()

            if not signal:
                log.error(f"Signal {signal_id} not found")
                return None

        factor_scores = {}
        try:
            if signal.factor_scores:
                factor_scores = json.loads(signal.factor_scores)
        except Exception:
            pass

        top_factors = sorted(
            factor_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
        top_factors_str = ", ".join(
            f"{k.replace('_', ' ')} ({v}pts)"
            for k, v in top_factors
        )

        rr = "--"
        try:
            if signal.entry and signal.sl and signal.tp1:
                risk   = abs(signal.entry - signal.sl)
                reward = abs(signal.tp1 - signal.entry)
                rr     = f"1:{round(reward/risk, 1)}" if risk > 0 else "--"
        except Exception:
            pass

        tone = _SIGNAL_TONES[signal_id % len(_SIGNAL_TONES)]

        signal_context = f"""
Signal Data:
- Coin: {signal.coin}USDT
- Direction: {signal.direction}
- Grade: {signal.grade}
- Score: {signal.score}/100
- Regime: {signal.regime or '--'}
- Session: {signal.session or '--'}
- Entry: {signal.entry}
- Stop Loss: {signal.sl}
- TP1: {signal.tp1}
- TP2: {signal.tp2}
- SL%: {f'{signal.sl_pct:.2f}%' if signal.sl_pct else '--'}
- Risk/Reward: {rr}
- Top Confluence Factors: {top_factors_str}
- Sweep Score: {signal.sweep_score}/12
- Displacement Score: {signal.disp_score}/11
- Market Score: {signal.market_score}/100
- Entry Score: {signal.entry_score}/100

Thesis:
{signal.notes or 'Strong confluence setup with institutional footprint confirmed.'}

Tone: {tone}
"""

        client = AsyncGroq(api_key=cfg.GROQ_API_KEY)

        response = await client.chat.completions.create(
            model    = "llama-3.3-70b-versatile",
            messages = [
                {"role": "system", "content": _SIGNAL_PROMPT},
                {"role": "user",   "content": signal_context}
            ],
            max_tokens  = 600,
            temperature = 0.7,
        )

        raw = response.choices[0].message.content.strip()

        try:
            start  = raw.find("{")
            end    = raw.rfind("}") + 1
            result = json.loads(raw[start:end]) if start >= 0 and end > start else {}
        except Exception:
            result = {}

        if not result.get("twitter_draft"):
            result = {
                "twitter_draft": f"{signal.coin}USDT {signal.direction} — Grade {signal.grade} signal. Score {signal.score}/100. Entry {signal.entry:.4f} | SL {signal.sl:.4f} | TP1 {signal.tp1:.4f} #Crypto #{signal.coin}",
                "long_draft":    f"{signal.coin}USDT {signal.direction} setup. Grade {signal.grade} with {signal.score}/100 confluence. Regime: {signal.regime}. Entry: {signal.entry} | SL: {signal.sl} | TP1: {signal.tp1} | TP2: {signal.tp2}. R:R {rr}.",
                "hashtags":      [f"#{signal.coin}", "#CryptoTrading", "#SignalEngine"],
                "tone_used":     tone
            }

        twitter_draft = result.get("twitter_draft", "")
        if len(twitter_draft) > 280:
            result["twitter_draft"] = twitter_draft[:277] + "..."

        result["signal_id"] = signal_id
        result["coin"]      = signal.coin
        result["direction"] = signal.direction
        result["grade"]     = signal.grade
        result["score"]     = signal.score
        result["post_type"] = "signal"

        log.info(
            f"Signal draft generated: {signal.coin} {signal.direction} "
            f"Grade:{signal.grade} tone:{tone} "
            f"chars:{len(result['twitter_draft'])}"
        )

        return result

    except Exception as e:
        log.error(f"Post draft generation error signal {signal_id}: {e}")
        return None


async def generate_commentary_draft(context: dict) -> dict | None:
    try:
        from config import cfg
        from groq import AsyncGroq

        if not cfg.GROQ_API_KEY:
            return None

        tone = _COMMENTARY_TONES[int(time.time()) % len(_COMMENTARY_TONES)]

        regime      = context.get("regime", "--")
        session     = context.get("session", "--")
        funding_avg = context.get("funding_avg", 0)
        fear_greed  = context.get("fear_greed", {})
        fg_val      = fear_greed.get("value", 50)
        fg_label    = fear_greed.get("label", "Neutral")
        top_coins   = context.get("top_coins", [])
        reason      = context.get("reason", "no tradeable setups")
        reason_code = context.get("reason_code", "")

        coins_str = ", ".join(
            f"{c['coin']} ({c['grade']} {c['score']}/100)"
            for c in top_coins[:3]
        ) if top_coins else "no coins with data"

        market_context = f"""
Current Market Conditions:
- Dominant Regime: {regime}
- Current Session: {session}
- Average Funding Rate: {funding_avg:.4f}%
- Fear & Greed: {fg_val}/100 — {fg_label}
- Scan Result: {reason}
- Trigger: {reason_code}
- Top Coins Scanned: {coins_str}

Write a commentary post about what the market is doing right now.
Do NOT give trade signals or entry/SL/TP levels.
Be observational, witty, or educational about the current market state.
Make it feel timely and human — like a trader watching the market right now.

Tone: {tone}
"""

        client = AsyncGroq(api_key=cfg.GROQ_API_KEY)

        response = await client.chat.completions.create(
            model    = "llama-3.3-70b-versatile",
            messages = [
                {"role": "system", "content": _COMMENTARY_PROMPT},
                {"role": "user",   "content": market_context}
            ],
            max_tokens  = 400,
            temperature = 0.9,
        )

        raw = response.choices[0].message.content.strip()

        try:
            start  = raw.find("{")
            end    = raw.rfind("}") + 1
            result = json.loads(raw[start:end]) if start >= 0 and end > start else {}
        except Exception:
            result = {}

        if not result.get("twitter_draft"):
            result = {
                "twitter_draft": f"Market scanning {len(top_coins)} coins. {reason}. {session} session. Regime: {regime}. Patience. #CryptoTrading",
                "long_draft":    f"Current market state: {regime} regime during {session}. Fear & Greed at {fg_val} ({fg_label}). Average funding {funding_avg:.4f}%. No high-conviction setups detected. Waiting for cleaner conditions.",
                "hashtags":      ["#CryptoTrading", "#Crypto"],
                "tone_used":     tone,
                "post_type":     "commentary"
            }

        twitter_draft = result.get("twitter_draft", "")
        if len(twitter_draft) > 280:
            result["twitter_draft"] = twitter_draft[:277] + "..."

        result["post_type"] = "commentary"
        result["signal_id"] = None
        result["coin"]      = "MARKET"
        result["direction"] = "--"
        result["grade"]     = "--"
        result["score"]     = 0

        log.info(
            f"Commentary draft generated: tone:{tone} "
            f"chars:{len(result['twitter_draft'])}"
        )

        return result

    except Exception as e:
        log.error(f"Commentary draft generation error: {e}")
        return None


def get_content_stats() -> dict:
    try:
        from database import SessionLocal, ContentPost
        with SessionLocal() as db:
            total     = db.query(ContentPost).count()
            pending   = db.query(ContentPost).filter(ContentPost.status == "pending").count()
            posted    = db.query(ContentPost).filter(ContentPost.status == "posted").count()
            discarded = db.query(ContentPost).filter(ContentPost.status == "discarded").count()

        return {
            "total":     total,
            "pending":   pending,
            "posted":    posted,
            "discarded": discarded
        }
    except Exception as e:
        log.error(f"Content stats error: {e}")
        return {}