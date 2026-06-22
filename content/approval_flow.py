import logging
import os
import time
from datetime import datetime, timezone, timedelta
from database import SessionLocal, ContentPost, Signal as SignalModel

log = logging.getLogger(__name__)

_COOLDOWN_HOURS_SAME_DIR  = 12
_COOLDOWN_HOURS_GRADE_UP  = 6


def _check_duplicate_cooldown(coin: str, direction: str, grade: str) -> tuple[bool, str]:
    try:
        with SessionLocal() as db:
            pending_signal = db.query(SignalModel).filter(
                SignalModel.coin      == coin,
                SignalModel.direction == direction,
                SignalModel.outcome   == "pending"
            ).first()

            if pending_signal:
                return True, f"{coin} {direction} trade still pending — no duplicate post"

            cutoff = datetime.now(timezone.utc) - timedelta(hours=_COOLDOWN_HOURS_SAME_DIR)

            recent = db.query(ContentPost).join(
                SignalModel, ContentPost.signal_id == SignalModel.id
            ).filter(
                SignalModel.coin      == coin,
                SignalModel.direction == direction,
                ContentPost.created_at >= cutoff
            ).first()

            if recent:
                elapsed = datetime.now(timezone.utc) - recent.created_at.replace(tzinfo=timezone.utc)
                hours_left = _COOLDOWN_HOURS_SAME_DIR - (elapsed.total_seconds() / 3600)
                return True, f"{coin} {direction} posted {elapsed.seconds // 3600}h ago — cooldown {hours_left:.1f}h remaining"

        return False, ""

    except Exception as e:
        log.error(f"Duplicate cooldown check error: {e}")
        return False, ""


async def send_for_approval(
    signal_id:  int,
    chart_path: str | None,
    draft:      dict
) -> bool:
    try:
        from alerts.telegram import _post
        from config import cfg

        if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
            log.error("Telegram not configured")
            return False

        post      = draft.get("post", "")
        tone_used = draft.get("tone_used", "mixed")
        coin      = draft.get("coin", "--")
        direction = draft.get("direction", "--")
        grade     = draft.get("grade", "--")
        score     = draft.get("score", 0)

        blocked, reason = _check_duplicate_cooldown(coin, direction, grade)
        if blocked:
            log.info(f"Content blocked — duplicate: {reason}")
            return False

        with SessionLocal() as db:
            existing = db.query(ContentPost).filter(
                ContentPost.signal_id == signal_id,
                ContentPost.status    == "pending"
            ).first()

            if existing:
                log.info(f"Content post already pending for signal {signal_id}")
                return False

            db_post = ContentPost(
                signal_id     = signal_id,
                chart_path    = chart_path,
                twitter_draft = post,
                long_draft    = None,
                hashtags      = None,
                tone_used     = tone_used,
                status        = "pending",
                platform      = "twitter"
            )
            db.add(db_post)
            db.flush()
            db.refresh(db_post)
            post_id = db_post.id
            db.commit()

        if chart_path and os.path.exists(chart_path):
            await _send_photo(
                chat_id    = cfg.TELEGRAM_CHAT_ID,
                photo_path = chart_path,
                caption    = f"📊 {coin}USDT {direction} — Grade `{grade}` · Score `{score}/100`"
            )

        char_count = len(post)
        char_color = "✅" if char_count <= 270 else "⚠️"

        message = (
            f"📝 *Post Ready — #{post_id}*\n\n"
            f"*{coin}USDT {direction}* — Grade `{grade}` · Score `{score}/100`\n"
            f"Tone: `{tone_used}` · {char_color} `{char_count}/270`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{post}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"_Copy and post manually. Reply `/discard {post_id}` to delete._"
        )

        await _post("sendMessage", {
            "chat_id":    cfg.TELEGRAM_CHAT_ID,
            "text":       message,
            "parse_mode": "Markdown"
        })

        log.info(f"Post sent to Telegram: post {post_id} signal {signal_id}")
        return True

    except Exception as e:
        log.error(f"send_for_approval error signal {signal_id}: {e}")
        return False


async def send_commentary_for_approval(draft: dict) -> bool:
    try:
        from alerts.telegram import _post
        from config import cfg

        if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
            return False

        post      = draft.get("post", "")
        tone_used = draft.get("tone_used", "mixed")

        with SessionLocal() as db:
            db_post = ContentPost(
                signal_id     = None,
                chart_path    = None,
                twitter_draft = post,
                long_draft    = None,
                hashtags      = None,
                tone_used     = tone_used,
                status        = "pending",
                platform      = "twitter"
            )
            db.add(db_post)
            db.flush()
            db.refresh(db_post)
            post_id = db_post.id
            db.commit()

        char_count = len(post)
        char_color = "✅" if char_count <= 270 else "⚠️"

        message = (
            f"💬 *Commentary Ready — #{post_id}*\n\n"
            f"Tone: `{tone_used}` · {char_color} `{char_count}/270`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{post}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"_Copy and post manually. Reply `/discard {post_id}` to delete._"
        )

        await _post("sendMessage", {
            "chat_id":    cfg.TELEGRAM_CHAT_ID,
            "text":       message,
            "parse_mode": "Markdown"
        })

        log.info(f"Commentary post sent: post {post_id}")
        return True

    except Exception as e:
        log.error(f"send_commentary_for_approval error: {e}")
        return False


async def send_brief_for_approval(draft: dict) -> bool:
    try:
        from alerts.telegram import _post
        from config import cfg

        if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
            return False

        post      = draft.get("post", "")
        tone_used = draft.get("tone_used", "professional")

        with SessionLocal() as db:
            db_post = ContentPost(
                signal_id     = None,
                chart_path    = None,
                twitter_draft = post,
                long_draft    = None,
                hashtags      = None,
                tone_used     = tone_used,
                status        = "pending",
                platform      = "twitter"
            )
            db.add(db_post)
            db.flush()
            db.refresh(db_post)
            post_id = db_post.id
            db.commit()

        char_count = len(post)
        char_color = "✅" if char_count <= 270 else "⚠️"

        message = (
            f"🌅 *Market Brief Ready — #{post_id}*\n\n"
            f"Tone: `{tone_used}` · {char_color} `{char_count}/270`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{post}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"_Copy and post manually. Reply `/discard {post_id}` to delete._"
        )

        await _post("sendMessage", {
            "chat_id":    cfg.TELEGRAM_CHAT_ID,
            "text":       message,
            "parse_mode": "Markdown"
        })

        log.info(f"Brief post sent: post {post_id}")
        return True

    except Exception as e:
        log.error(f"send_brief_for_approval error: {e}")
        return False


async def _send_photo(chat_id: str, photo_path: str, caption: str = ""):
    try:
        import httpx
        from config import cfg

        BASE = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}"

        with open(photo_path, "rb") as f:
            photo_bytes = f.read()

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{BASE}/sendPhoto",
                data  = {
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


async def discard_post(post_id: int) -> bool:
    try:
        with SessionLocal() as db:
            post = db.query(ContentPost).filter(
                ContentPost.id == post_id
            ).first()

            if not post:
                return False

            post.status = "discarded"
            db.commit()

        log.info(f"Post {post_id} discarded")
        return True

    except Exception as e:
        log.error(f"discard_post error: {e}")
        return False


async def get_post_text(post_id: int) -> str | None:
    try:
        with SessionLocal() as db:
            post = db.query(ContentPost).filter(
                ContentPost.id == post_id
            ).first()

            if not post:
                return None

            return post.twitter_draft

    except Exception as e:
        log.error(f"get_post_text error: {e}")
        return None


async def get_pending_posts() -> list:
    try:
        with SessionLocal() as db:
            posts = db.query(ContentPost).filter(
                ContentPost.status == "pending"
            ).order_by(ContentPost.created_at.desc()).all()

            result = []
            for p in posts:
                signal = None
                if p.signal_id:
                    signal = db.query(SignalModel).filter(
                        SignalModel.id == p.signal_id
                    ).first()

                result.append({
                    "post_id":       p.id,
                    "signal_id":     p.signal_id,
                    "coin":          signal.coin      if signal else "MARKET",
                    "direction":     signal.direction if signal else "--",
                    "grade":         signal.grade     if signal else "--",
                    "post":          p.twitter_draft or "",
                    "tone_used":     p.tone_used,
                    "post_type":     "signal" if p.signal_id else "commentary",
                    "created_at":    p.created_at.isoformat() if p.created_at else "--",
                    "chart_path":    p.chart_path
                })

            return result

    except Exception as e:
        log.error(f"get_pending_posts error: {e}")
        return []


def purge_old_content(days: int = 7):
    try:
        import os
        from pathlib import Path

        cutoff_db    = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_chart = datetime.now(timezone.utc) - timedelta(hours=48)

        with SessionLocal() as db:
            old_posts = db.query(ContentPost).filter(
                ContentPost.created_at <= cutoff_db,
                ContentPost.status.in_(["discarded", "posted"])
            ).all()

            deleted_db = 0
            for post in old_posts:
                if post.chart_path and os.path.exists(post.chart_path):
                    try:
                        os.remove(post.chart_path)
                    except Exception:
                        pass
                db.delete(post)
                deleted_db += 1

            db.commit()

        chart_dir = Path("content/charts")
        deleted_charts = 0
        if chart_dir.exists():
            for f in chart_dir.iterdir():
                if f.is_file() and f.suffix == ".png":
                    mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                    if mtime < cutoff_chart:
                        try:
                            f.unlink()
                            deleted_charts += 1
                        except Exception:
                            pass

        log.info(f"Purge complete: {deleted_db} db records, {deleted_charts} chart images deleted")

    except Exception as e:
        log.error(f"purge_old_content error: {e}")