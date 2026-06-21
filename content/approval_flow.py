import logging
import os
from datetime import datetime, timezone
from database import SessionLocal, ContentPost, Signal as SignalModel

log = logging.getLogger(__name__)


async def send_for_approval(
    signal_id:  int,
    chart_path: str | None,
    draft:      dict
) -> bool:
    """
    Send chart + draft to Telegram for approval.
    Returns True if sent successfully.
    """
    try:
        from alerts.telegram import send, _post
        from config import cfg

        if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
            log.error("Telegram not configured")
            return False

        # Save to DB first
        twitter_draft = draft.get("twitter_draft", "")
        long_draft    = draft.get("long_draft", "")
        hashtags      = str(draft.get("hashtags", []))
        tone_used     = draft.get("tone_used", "professional")
        coin          = draft.get("coin", "--")
        direction     = draft.get("direction", "--")
        grade         = draft.get("grade", "--")
        score         = draft.get("score", 0)

        with SessionLocal() as db:
            existing = db.query(ContentPost).filter(
                ContentPost.signal_id == signal_id,
                ContentPost.status    == "pending"
            ).first()

            if existing:
                log.info(f"Content post already pending for signal {signal_id}")
                return False

            post = ContentPost(
                signal_id     = signal_id,
                chart_path    = chart_path,
                twitter_draft = twitter_draft,
                long_draft    = long_draft,
                hashtags      = hashtags,
                tone_used     = tone_used,
                status        = "pending",
                platform      = "twitter"
            )
            db.add(post)
            db.flush()
            db.refresh(post)
            post_id = post.id

        log.info(f"ContentPost created: id={post_id} signal={signal_id}")

        # Send chart image if available
        if chart_path and os.path.exists(chart_path):
            await _send_photo(
                chat_id    = cfg.TELEGRAM_CHAT_ID,
                photo_path = chart_path,
                caption    = f"📊 *{coin}USDT {direction}* — Grade `{grade}` · Score `{score}/100`"
            )

        # Send approval message with keyboard
        char_count = len(twitter_draft)
        char_color = "✅" if char_count <= 280 else "⚠️"

        message = (
            f"📝 *New Post Ready for Approval*\n\n"
            f"*{coin}USDT {direction}* — Grade `{grade}` · Score `{score}/100`\n"
            f"Tone: `{tone_used}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*Twitter Draft* {char_color} `{char_count}/280`:\n\n"
            f"{twitter_draft}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*Long Form:*\n\n"
            f"{long_draft[:300]}{'...' if len(long_draft) > 300 else ''}\n"
        )

        keyboard = [
            [
                {"text": "✅ Approve & Post",  "callback_data": f"approve_post:{post_id}"},
                {"text": "❌ Discard",          "callback_data": f"discard_post:{post_id}"}
            ],
            [
                {"text": "✏️ Edit Draft",       "callback_data": f"edit_post:{post_id}"},
                {"text": "🔄 Regenerate",       "callback_data": f"regen_post:{post_id}"}
            ]
        ]

        await _post("sendMessage", {
            "chat_id":      cfg.TELEGRAM_CHAT_ID,
            "text":         message,
            "parse_mode":   "Markdown",
            "reply_markup": {"inline_keyboard": keyboard}
        })

        log.info(f"Approval message sent for post {post_id} signal {signal_id}")
        return True

    except Exception as e:
        log.error(f"send_for_approval error signal {signal_id}: {e}")
        return False


async def _send_photo(chat_id: str, photo_path: str, caption: str = ""):
    """Send photo to Telegram chat."""
    try:
        import httpx
        from config import cfg

        BASE = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}"

        with open(photo_path, "rb") as f:
            photo_bytes = f.read()

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{BASE}/sendPhoto",
                data    = {
                    "chat_id":    chat_id,
                    "caption":    caption,
                    "parse_mode": "Markdown"
                },
                files   = {"photo": ("chart.png", photo_bytes, "image/png")},
                timeout = 30
            )
            if r.status_code != 200:
                log.error(f"Photo send failed: {r.text}")
    except Exception as e:
        log.error(f"Send photo error: {e}")


async def handle_approve_post(post_id: int):
    """Handle approve button callback."""
    try:
        from alerts.telegram import send
        from content.publisher import post_to_twitter

        with SessionLocal() as db:
            post = db.query(ContentPost).filter(
                ContentPost.id == post_id
            ).first()

            if not post:
                await send(f"⚠️ Post #{post_id} not found.")
                return

            if post.status != "pending":
                await send(f"⚠️ Post #{post_id} already {post.status}.")
                return

            draft_text = post.edited_text or post.twitter_draft
            chart_path = post.chart_path
            signal_id  = post.signal_id

        await send(f"⏳ Posting to Twitter...")

        result = await post_to_twitter(
            post_id    = post_id,
            text       = draft_text,
            chart_path = chart_path
        )

        if result.get("success"):
            tweet_id = result.get("tweet_id", "")
            await send(
                f"✅ *Posted to Twitter*\n\n"
                f"Post #{post_id} · Signal #{signal_id}\n"
                f"Tweet ID: `{tweet_id}`\n"
                f"[View Tweet](https://twitter.com/i/web/status/{tweet_id})"
            )
        else:
            await send(
                f"❌ *Twitter Post Failed*\n\n"
                f"Post #{post_id}\n"
                f"Reason: `{result.get('reason', 'Unknown error')}`"
            )

    except Exception as e:
        log.error(f"handle_approve_post error: {e}")
        from alerts.telegram import send
        await send(f"❌ Approve failed: `{str(e)}`")


async def handle_discard_post(post_id: int):
    """Handle discard button callback."""
    try:
        from alerts.telegram import send

        with SessionLocal() as db:
            post = db.query(ContentPost).filter(
                ContentPost.id == post_id
            ).first()

            if not post:
                await send(f"⚠️ Post #{post_id} not found.")
                return

            post.status = "discarded"
            db.commit()

        await send(f"🗑️ Post #{post_id} discarded.")
        log.info(f"Post {post_id} discarded")

    except Exception as e:
        log.error(f"handle_discard_post error: {e}")


async def handle_edit_post(post_id: int):
    """Handle edit button callback — prompts user to send new text."""
    try:
        from alerts.telegram import send
        import runtime_state as rs

        rs.set("pending_edit_post_id", post_id)

        await send(
            f"✏️ *Edit Post #{post_id}*\n\n"
            f"Send your edited tweet text now.\n"
            f"Must be under 280 characters.\n\n"
            f"Send /canceledit to cancel."
        )
    except Exception as e:
        log.error(f"handle_edit_post error: {e}")


async def handle_regen_post(post_id: int):
    """Handle regenerate button callback."""
    try:
        from alerts.telegram import send
        from content.groq_writer import generate_post_draft

        with SessionLocal() as db:
            post = db.query(ContentPost).filter(
                ContentPost.id == post_id
            ).first()
            if not post:
                await send(f"⚠️ Post #{post_id} not found.")
                return
            signal_id = post.signal_id

        await send("🔄 Regenerating draft...")

        new_draft = await generate_post_draft(signal_id)
        if not new_draft:
            await send("❌ Regeneration failed.")
            return

        with SessionLocal() as db:
            post = db.query(ContentPost).filter(
                ContentPost.id == post_id
            ).first()
            if post:
                post.twitter_draft = new_draft.get("twitter_draft", post.twitter_draft)
                post.long_draft    = new_draft.get("long_draft",    post.long_draft)
                post.tone_used     = new_draft.get("tone_used",     post.tone_used)
                post.edited_text   = None
                db.commit()

        chart_path = post.chart_path if post else None
        await send_for_approval(signal_id, chart_path, new_draft)
        await send(f"✅ New draft ready for post #{post_id}")

    except Exception as e:
        log.error(f"handle_regen_post error: {e}")


async def apply_edit_to_post(post_id: int, new_text: str):
    """Apply edited text to a pending post."""
    try:
        from alerts.telegram import send

        if len(new_text) > 280:
            await send(
                f"⚠️ Text too long: `{len(new_text)}/280` characters.\n"
                f"Please shorten and try again."
            )
            return False

        with SessionLocal() as db:
            post = db.query(ContentPost).filter(
                ContentPost.id == post_id
            ).first()
            if not post:
                await send(f"⚠️ Post #{post_id} not found.")
                return False

            post.edited_text = new_text
            db.commit()

        await send(
            f"✅ *Draft Updated*\n\n"
            f"Post #{post_id} · `{len(new_text)}/280` chars\n\n"
            f"{new_text}\n\n"
            f"Tap Approve to post.",
            )

        keyboard = [
            [
                {"text": "✅ Approve & Post", "callback_data": f"approve_post:{post_id}"},
                {"text": "❌ Discard",         "callback_data": f"discard_post:{post_id}"}
            ]
        ]

        from alerts.telegram import _post
        from config import cfg
        await _post("sendMessage", {
            "chat_id":      cfg.TELEGRAM_CHAT_ID,
            "text":         f"Updated draft ready:",
            "parse_mode":   "Markdown",
            "reply_markup": {"inline_keyboard": keyboard}
        })

        return True

    except Exception as e:
        log.error(f"apply_edit_to_post error: {e}")
        return False


async def get_pending_posts() -> list:
    """Get all pending posts."""
    try:
        with SessionLocal() as db:
            posts = db.query(ContentPost).filter(
                ContentPost.status == "pending"
            ).order_by(ContentPost.created_at.desc()).all()

            result = []
            for p in posts:
                signal = db.query(SignalModel).filter(
                    SignalModel.id == p.signal_id
                ).first()

                result.append({
                    "post_id":      p.id,
                    "signal_id":    p.signal_id,
                    "coin":         signal.coin if signal else "--",
                    "direction":    signal.direction if signal else "--",
                    "grade":        signal.grade if signal else "--",
                    "twitter_draft": p.twitter_draft,
                    "tone_used":    p.tone_used,
                    "created_at":   p.created_at.isoformat() if p.created_at else "--",
                    "chart_path":   p.chart_path
                })

            return result

    except Exception as e:
        log.error(f"get_pending_posts error: {e}")
        return []