import json
import logging
import time
from datetime import datetime, timezone
from database import SessionLocal, Signal as SignalModel

log = logging.getLogger(__name__)

_SIGNAL_PROMPT = """You are a crypto trading analyst writing for Twitter/X for Signal Engine v5.

RULES:
- Maximum 270 characters total including hashtags
- Be specific — use actual prices, grades, scores from the signal
- No financial advice disclaimers
- No "I" statements
- Include coin, direction, key level, and why it matters
- End with exactly 3 relevant hashtags on a new line
- Pick the most fitting tone based on signal context: professional, educational, humor, witty, or quirky
- Make it feel human, not robotic
- One single finalized post — no drafts, no versions

TONE GUIDE:
- professional: factual, data-driven, concise, hedge fund analyst voice
- educational: explain the setup for beginners, use simple analogies
- humor: dry wit, sarcastic, crypto twitter native, punchy one-liners
- witty: clever wordplay, sharp observation, still includes real data
- quirky: unexpected angle, personality-driven, memorable

OUTPUT FORMAT (JSON only, no other text):
{
  "post": "...",
  "tone_used": "professional"
}"""


_COMMENTARY_PROMPT = """You are a witty crypto market commentator writing for Twitter/X for Signal Engine v5.

RULES:
- Maximum 270 characters total including hashtags
- Write about what the MARKET IS DOING right now — not trade signals
- No entry/SL/TP levels
- Be conversational, observational, sometimes educational
- Reference actual market data provided
- End with exactly 3 relevant hashtags on a new line
- Pick the most fitting tone: humor, educational, witty, quirky, or professional
- One single finalized post — no drafts, no versions

OUTPUT FORMAT (JSON only, no other text):
{
  "post": "...",
  "tone_used": "humor"
}"""


def _pick_tone_hint(signal_data: dict) -> str:
    score   = signal_data.get("score", 0)
    grade   = signal_data.get("grade", "F")
    session = signal_data.get("session", "")
    regime  = signal_data.get("regime", "")

    if grade == "A+" and score >= 90:
        return "punchy/witty — this is a strong signal, make it exciting"
    if "London/NY" in session:
        return "professional — peak session, institutional feel"
    if "CHOP" in regime.upper():
        return "humor — market is choppy, be sarcastic about it"
    if score >= 80:
        return "educational — strong setup, good teaching moment"
    return "mixed — pick whatever fits best"


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

        tone_hint = _pick_tone_hint({
            "score":   signal.score or 0,
            "grade":   signal.grade or "F",
            "session": signal.session or "",
            "regime":  signal.regime or ""
        })

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
- TP: {signal.tp1}
- SL%: {f'{signal.sl_pct:.2f}%' if signal.sl_pct else '--'}
- Risk/Reward: {rr}
- Top Confluence Factors: {top_factors_str}
- Sweep Score: {signal.sweep_score}/12
- Displacement Score: {signal.disp_score}/11

Tone hint: {tone_hint}

Write ONE finalized post under 270 chars including hashtags.
"""

        client = AsyncGroq(api_key=cfg.GROQ_API_KEY)

        response = await client.chat.completions.create(
            model    = "llama-3.3-70b-versatile",
            messages = [
                {"role": "system", "content": _SIGNAL_PROMPT},
                {"role": "user",   "content": signal_context}
            ],
            max_tokens  = 300,
            temperature = 0.8,
        )

        raw = response.choices[0].message.content.strip()

        try:
            start  = raw.find("{")
            end    = raw.rfind("}") + 1
            result = json.loads(raw[start:end]) if start >= 0 and end > start else {}
        except Exception:
            result = {}

        post = result.get("post", "")

        if not post:
            post = (
                f"{signal.coin}USDT {signal.direction} — Grade {signal.grade} · Score {signal.score}/100\n"
                f"Entry {signal.entry:.4f} | SL {signal.sl:.4f} | TP {signal.tp1:.4f} | R:R {rr}\n"
                f"#{signal.coin} #CryptoTrading #SmartMoney"
            )

        if len(post) > 270:
            post = post[:267] + "..."

        return {
            "post":      post,
            "tone_used": result.get("tone_used", "mixed"),
            "signal_id": signal_id,
            "coin":      signal.coin,
            "direction": signal.direction,
            "grade":     signal.grade,
            "score":     signal.score,
            "post_type": "signal"
        }

    except Exception as e:
        log.error(f"Post draft generation error signal {signal_id}: {e}")
        return None


async def generate_commentary_draft(context: dict) -> dict | None:
    try:
        from config import cfg
        from groq import AsyncGroq

        if not cfg.GROQ_API_KEY:
            return None

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

        tone_hint = "humor" if "chop" in regime.lower() else "mixed"
        if fg_val <= 20:
            tone_hint = "educational — extreme fear, explain what it means"
        elif fg_val >= 80:
            tone_hint = "witty — extreme greed, be cautious but clever"

        market_context = f"""
Current Market Conditions:
- Dominant Regime: {regime}
- Current Session: {session}
- Average Funding Rate: {funding_avg:.4f}%
- Fear & Greed: {fg_val}/100 — {fg_label}
- Scan Result: {reason}
- Trigger: {reason_code}
- Top Coins Scanned: {coins_str}

Tone hint: {tone_hint}

Write ONE finalized commentary post under 270 chars including hashtags.
Do NOT give trade signals or entry/SL/TP levels.
"""

        client = AsyncGroq(api_key=cfg.GROQ_API_KEY)

        response = await client.chat.completions.create(
            model    = "llama-3.3-70b-versatile",
            messages = [
                {"role": "system", "content": _COMMENTARY_PROMPT},
                {"role": "user",   "content": market_context}
            ],
            max_tokens  = 300,
            temperature = 0.9,
        )

        raw = response.choices[0].message.content.strip()

        try:
            start  = raw.find("{")
            end    = raw.rfind("}") + 1
            result = json.loads(raw[start:end]) if start >= 0 and end > start else {}
        except Exception:
            result = {}

        post = result.get("post", "")

        if not post:
            post = (
                f"Market scanning {len(top_coins)} coins. {reason}. "
                f"{session} · Regime: {regime} · F&G: {fg_val} ({fg_label})\n"
                f"#CryptoTrading #Crypto #Bitcoin"
            )

        if len(post) > 270:
            post = post[:267] + "..."

        return {
            "post":      post,
            "tone_used": result.get("tone_used", "mixed"),
            "post_type": "commentary",
            "signal_id": None,
            "coin":      "MARKET",
            "direction": "--",
            "grade":     "--",
            "score":     0
        }

    except Exception as e:
        log.error(f"Commentary draft generation error: {e}")
        return None


async def generate_brief_post(context: dict) -> dict | None:
    try:
        from config import cfg
        from groq import AsyncGroq

        if not cfg.GROQ_API_KEY:
            return None

        _BRIEF_PROMPT = """You are a crypto market analyst writing a morning/evening market brief for Twitter/X.

RULES:
- Maximum 270 characters total including hashtags
- Summarize current market state: regime, session, top setups, sentiment
- Mention BTC direction, fear/greed, and 1-2 top coins if available
- End with exactly 3 hashtags
- Tone: informative but engaging, like a trader's morning note
- One single finalized post

OUTPUT FORMAT (JSON only):
{
  "post": "...",
  "tone_used": "professional"
}"""

        regime     = context.get("regime", "--")
        session    = context.get("session", "--")
        fg_val     = context.get("fg_val", 50)
        fg_label   = context.get("fg_label", "Neutral")
        btc_change = context.get("btc_change", 0)
        top_coins  = context.get("top_coins", [])
        time_label = context.get("time_label", "Morning")

        coins_str = ", ".join(
            f"{c['coin']} Grade {c['grade']}"
            for c in top_coins[:2]
        ) if top_coins else "no setups"

        brief_context = f"""
{time_label} Brief Data:
- BTC 24h: {'+' if btc_change >= 0 else ''}{btc_change:.2f}%
- Regime: {regime}
- Session: {session}
- Fear & Greed: {fg_val}/100 — {fg_label}
- Top Setups: {coins_str}

Write ONE finalized market brief post under 270 chars.
"""

        client = AsyncGroq(api_key=cfg.GROQ_API_KEY)

        response = await client.chat.completions.create(
            model    = "llama-3.3-70b-versatile",
            messages = [
                {"role": "system", "content": _BRIEF_PROMPT},
                {"role": "user",   "content": brief_context}
            ],
            max_tokens  = 300,
            temperature = 0.7,
        )

        raw = response.choices[0].message.content.strip()

        try:
            start  = raw.find("{")
            end    = raw.rfind("}") + 1
            result = json.loads(raw[start:end]) if start >= 0 and end > start else {}
        except Exception:
            result = {}

        post = result.get("post", "")

        if not post:
            sign = "+" if btc_change >= 0 else ""
            post = (
                f"{time_label} Brief: BTC {sign}{btc_change:.2f}% · "
                f"Regime: {regime} · F&G: {fg_val} ({fg_label})\n"
                f"Top setups: {coins_str}\n"
                f"#Bitcoin #CryptoTrading #Crypto"
            )

        if len(post) > 270:
            post = post[:267] + "..."

        return {
            "post":      post,
            "tone_used": result.get("tone_used", "professional"),
            "post_type": "brief"
        }

    except Exception as e:
        log.error(f"Brief post generation error: {e}")
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