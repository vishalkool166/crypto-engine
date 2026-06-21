import asyncio
import logging
import time
from datetime import datetime, timezone
from config import cfg

log = logging.getLogger(__name__)

_last_commentary_time = 0.0


def _get_commentary_cooldown() -> int:
    now  = datetime.now(timezone.utc)
    hour = now.hour + now.minute / 60

    london_ny_overlap = 13 <= hour < 16
    london            = 8  <= hour < 16
    ny                = 16 <= hour < 21
    weekend           = now.weekday() >= 5

    if weekend:
        return 8 * 3600
    if london_ny_overlap:
        return 1 * 3600
    if london or ny:
        return 2 * 3600
    return 6 * 3600


def _is_interesting_market(results: list, fg: dict) -> tuple[bool, str]:
    fg_val = fg.get("value", 50)

    if fg_val <= 20:
        return True, f"extreme_fear_{fg_val}"
    if fg_val >= 80:
        return True, f"extreme_greed_{fg_val}"

    if not results:
        return False, ""

    choppy = sum(1 for r in results if "CHOP" in r.get("regime", "").upper())
    if choppy >= len(results) * 0.7:
        return True, "market_choppy"

    fundings = [abs(r.get("market", {}).get("funding", 0) * 100) for r in results]
    avg_fund = sum(fundings) / len(fundings) if fundings else 0
    if avg_fund > 0.06:
        return True, f"extreme_funding_{avg_fund:.3f}"

    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return True, "weekend_market"

    return False, ""


async def run_content_pipeline(signal_id: int):
    if not cfg.CONTENT_ENABLED:
        return

    log.info(f"Content pipeline started: signal {signal_id}")

    try:
        chart_path = None
        try:
            from content.chart_engine import generate_signal_chart
            chart_path = generate_signal_chart(signal_id)
            if chart_path:
                log.info(f"Chart generated: {chart_path}")
            else:
                log.warning(f"Chart generation failed signal {signal_id} — continuing without chart")
        except Exception as e:
            log.error(f"Chart engine error signal {signal_id}: {e}")

        draft = None
        try:
            from content.groq_writer import generate_post_draft
            draft = await generate_post_draft(signal_id)
            if draft:
                log.info(f"Draft generated: signal {signal_id} tone:{draft.get('tone_used')}")
            else:
                log.warning(f"Draft generation failed signal {signal_id}")
                return
        except Exception as e:
            log.error(f"Groq writer error signal {signal_id}: {e}")
            return

        if cfg.CONTENT_AUTO_APPROVE:
            try:
                from content.publisher import post_to_twitter
                from database import SessionLocal, ContentPost

                twitter_draft = draft.get("twitter_draft", "")

                with SessionLocal() as db:
                    post = ContentPost(
                        signal_id     = signal_id,
                        chart_path    = chart_path,
                        twitter_draft = twitter_draft,
                        long_draft    = draft.get("long_draft", ""),
                        hashtags      = str(draft.get("hashtags", [])),
                        tone_used     = draft.get("tone_used", "professional"),
                        status        = "pending",
                        platform      = "twitter"
                    )
                    db.add(post)
                    db.flush()
                    db.refresh(post)
                    post_id = post.id

                result = await post_to_twitter(
                    post_id    = post_id,
                    text       = twitter_draft,
                    chart_path = chart_path
                )

                if result.get("success"):
                    from alerts.telegram import send
                    await send(
                        f"✅ *Auto-Posted to Twitter*\n\n"
                        f"Signal #{signal_id}\n"
                        f"Tweet: {result.get('tweet_url', '--')}"
                    )
            except Exception as e:
                log.error(f"Auto-approve error signal {signal_id}: {e}")
        else:
            try:
                from content.approval_flow import send_for_approval
                await send_for_approval(signal_id, chart_path, draft)
            except Exception as e:
                log.error(f"Approval flow error signal {signal_id}: {e}")

        log.info(f"Content pipeline complete: signal {signal_id}")

    except Exception as e:
        log.error(f"Content pipeline error signal {signal_id}: {e}")


async def run_commentary_pipeline(scan_results: list):
    global _last_commentary_time

    if not cfg.CONTENT_ENABLED:
        return

    now      = time.time()
    cooldown = _get_commentary_cooldown()

    if now - _last_commentary_time < cooldown:
        remaining = int((cooldown - (now - _last_commentary_time)) / 60)
        log.debug(f"Commentary cooldown — {remaining}m remaining")
        return

    try:
        from data.fetcher import get_fear_greed

        fg = {"value": 50, "label": "Neutral"}
        try:
            fg = await get_fear_greed()
        except Exception:
            pass

        interesting, reason_code = _is_interesting_market(scan_results, fg)
        if not interesting:
            log.debug("Market not interesting enough for commentary — skipping")
            return

        _last_commentary_time = now

        funding_values = []
        top_coins      = []

        for r in scan_results[:5]:
            market  = r.get("market", {})
            funding = market.get("funding", 0) * 100
            funding_values.append(funding)
            top_coins.append({
                "coin":      r.get("coin", "--"),
                "grade":     r.get("grade", "F"),
                "score":     r.get("score", 0),
                "direction": r.get("direction", "--"),
                "regime":    r.get("regime", "--")
            })

        funding_avg     = sum(funding_values) / len(funding_values) if funding_values else 0
        regimes         = [r.get("regime", "") for r in scan_results if r.get("regime")]
        dominant_regime = max(set(regimes), key=regimes.count) if regimes else "Unknown"
        sessions        = [r.get("session", "") for r in scan_results if r.get("session")]
        session         = sessions[0] if sessions else "Unknown"

        choppy_count  = sum(1 for r in scan_results if "CHOP" in r.get("regime", "").upper())
        ranging_count = sum(1 for r in scan_results if "RANG" in r.get("regime", "").upper())

        if choppy_count > len(scan_results) * 0.5:
            reason = f"{choppy_count}/{len(scan_results)} coins in choppy regime"
        elif ranging_count > len(scan_results) * 0.5:
            reason = f"{ranging_count}/{len(scan_results)} coins ranging"
        else:
            reason = "no high-confluence setups detected"

        context = {
            "regime":      dominant_regime,
            "session":     session,
            "funding_avg": funding_avg,
            "fear_greed":  fg,
            "top_coins":   top_coins,
            "reason":      reason,
            "reason_code": reason_code
        }

        from content.groq_writer import generate_commentary_draft
        draft = await generate_commentary_draft(context)

        if not draft:
            log.warning("Commentary draft generation failed")
            return

        from content.approval_flow import send_commentary_for_approval
        await send_commentary_for_approval(draft)

        log.info(f"Commentary pipeline complete: tone:{draft.get('tone_used')} reason:{reason_code}")

    except Exception as e:
        log.error(f"Commentary pipeline error: {e}")