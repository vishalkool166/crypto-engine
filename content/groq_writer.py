import json
import logging
from database import SessionLocal, Signal as SignalModel

log = logging.getLogger(__name__)

_PROFESSIONAL_PROMPT = """You are a professional crypto trading analyst writing for Twitter/X.

RULES:
- Maximum 280 characters for twitter_draft
- Be specific — use actual prices, grades, scores from the signal
- Sound like a professional trader not a bot
- No emojis overload — max 2-3 per post
- No financial advice disclaimers in the post itself
- No "I" statements — write in third person or impersonal
- Include coin, direction, key level, and why it matters
- End with 2-3 relevant hashtags
- long_draft is for detailed analysis — 500-800 characters
- long_draft includes full thesis, key levels, confluence factors

TONE ROTATION:
- professional: factual, data-driven, concise
- educational: explain the setup for beginners
- analytical: deep dive into confluence factors

OUTPUT FORMAT (JSON only, no other text):
{
  "twitter_draft": "...",
  "long_draft": "...",
  "hashtags": ["#BTC", "#CryptoTrading"],
  "tone_used": "professional"
}"""


async def generate_post_draft(signal_id: int) -> dict | None:
    """
    Generate social media post draft for a signal.
    Returns dict with twitter_draft, long_draft, hashtags.
    """
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

        # Parse factor scores
        factor_scores = {}
        try:
            if signal.factor_scores:
                factor_scores = json.loads(signal.factor_scores)
        except Exception:
            pass

        # Top 3 factors
        top_factors = sorted(
            factor_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
        top_factors_str = ", ".join(
            f"{k.replace('_', ' ')} ({v}pts)"
            for k, v in top_factors
        )

        # Risk reward
        rr = "--"
        try:
            if signal.entry and signal.sl and signal.tp1:
                risk   = abs(signal.entry - signal.sl)
                reward = abs(signal.tp1 - signal.entry)
                rr     = f"1:{round(reward/risk, 1)}" if risk > 0 else "--"
        except Exception:
            pass

        # Tone rotation based on signal_id
        tones = ["professional", "educational", "analytical"]
        tone  = tones[signal_id % 3]

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
- SL%: {signal.sl_pct:.2f}% if {signal.sl_pct} else '--'
- Risk/Reward: {rr}
- Top Confluence Factors: {top_factors_str}
- Sweep Score: {signal.sweep_score}/12
- Displacement Score: {signal.disp_score}/11
- Market Score: {signal.market_score}/100
- Entry Score: {signal.entry_score}/100

Thesis (use this as basis for the post):
{signal.notes or 'Strong confluence setup with institutional footprint confirmed.'}

Tone: {tone}
Platform: Twitter/X
"""

        client = AsyncGroq(api_key=cfg.GROQ_API_KEY)

        response = await client.chat.completions.create(
            model    = "llama-3.3-70b-versatile",
            messages = [
                {"role": "system", "content": _PROFESSIONAL_PROMPT},
                {"role": "user",   "content": signal_context}
            ],
            max_tokens  = 600,
            temperature = 0.7,
        )

        raw = response.choices[0].message.content.strip()

        # Parse JSON response
        try:
            # Find JSON block
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(raw[start:end])
            else:
                raise ValueError("No JSON found in response")
        except Exception as e:
            log.error(f"Failed to parse Groq response: {e}\nRaw: {raw}")
            # Fallback draft
            result = {
                "twitter_draft": f"{signal.coin}USDT {signal.direction} — Grade {signal.grade} signal. Score {signal.score}/100. Entry {signal.entry:.4f} | SL {signal.sl:.4f} | TP1 {signal.tp1:.4f} #Crypto #{signal.coin}",
                "long_draft":    f"{signal.coin}USDT {signal.direction} setup. Grade {signal.grade} with {signal.score}/100 confluence score. Regime: {signal.regime}. Entry: {signal.entry} | SL: {signal.sl} | TP1: {signal.tp1} | TP2: {signal.tp2}. R:R {rr}.",
                "hashtags":      [f"#{signal.coin}", "#CryptoTrading", "#SignalEngine"],
                "tone_used":     tone
            }

        # Enforce 280 char limit on twitter_draft
        twitter_draft = result.get("twitter_draft", "")
        if len(twitter_draft) > 280:
            twitter_draft = twitter_draft[:277] + "..."
            result["twitter_draft"] = twitter_draft

        result["signal_id"] = signal_id
        result["coin"]      = signal.coin
        result["direction"] = signal.direction
        result["grade"]     = signal.grade
        result["score"]     = signal.score

        log.info(
            f"Post draft generated: {signal.coin} {signal.direction} "
            f"Grade:{signal.grade} tone:{tone} "
            f"chars:{len(twitter_draft)}"
        )

        return result

    except Exception as e:
        log.error(f"Post draft generation error signal {signal_id}: {e}")
        return None


def get_content_stats() -> dict:
    """Returns content posting statistics."""
    try:
        from database import SessionLocal
        from database import ContentPost
        with SessionLocal() as db:
            total    = db.query(ContentPost).count()
            pending  = db.query(ContentPost).filter(ContentPost.status == "pending").count()
            posted   = db.query(ContentPost).filter(ContentPost.status == "posted").count()
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