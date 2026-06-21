import asyncio
import logging
from config import cfg

log = logging.getLogger(__name__)


async def run_content_pipeline(signal_id: int):
    """
    Full content pipeline for a signal.
    Non-blocking — called via asyncio.create_task().

    Steps:
    1. Generate chart
    2. Generate Groq draft
    3. Send for Telegram approval
    """
    if not cfg.CONTENT_ENABLED:
        return

    log.info(f"Content pipeline started: signal {signal_id}")

    try:
        # Step 1 — Generate chart
        chart_path = None
        try:
            from content.chart_engine import generate_signal_chart
            chart_path = generate_signal_chart(signal_id)
            if chart_path:
                log.info(f"Chart generated: {chart_path}")
            else:
                log.warning(f"Chart generation failed for signal {signal_id} — continuing without chart")
        except Exception as e:
            log.error(f"Chart engine error signal {signal_id}: {e}")

        # Step 2 — Generate Groq draft
        draft = None
        try:
            from content.groq_writer import generate_post_draft
            draft = await generate_post_draft(signal_id)
            if draft:
                log.info(f"Draft generated: signal {signal_id} tone:{draft.get('tone_used')}")
            else:
                log.warning(f"Draft generation failed for signal {signal_id}")
                return
        except Exception as e:
            log.error(f"Groq writer error signal {signal_id}: {e}")
            return

        # Step 3 — Auto approve or send for approval
        if cfg.CONTENT_AUTO_APPROVE:
            try:
                from content.publisher import post_to_twitter
                from database import SessionLocal, ContentPost
                from datetime import datetime, timezone

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
                else:
                    log.error(f"Auto-post failed: {result.get('reason')}")

            except Exception as e:
                log.error(f"Auto-approve error signal {signal_id}: {e}")

        else:
            # Send for manual approval
            try:
                from content.approval_flow import send_for_approval
                await send_for_approval(signal_id, chart_path, draft)
            except Exception as e:
                log.error(f"Approval flow error signal {signal_id}: {e}")

        log.info(f"Content pipeline complete: signal {signal_id}")

    except Exception as e:
        log.error(f"Content pipeline error signal {signal_id}: {e}")