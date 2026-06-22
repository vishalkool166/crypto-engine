import logging
import json
from datetime import datetime, timezone
from database import SessionLocal, ContentPost

log = logging.getLogger(__name__)


def mark_as_posted(post_id: int, note: str = "") -> bool:
    try:
        with SessionLocal() as db:
            post = db.query(ContentPost).filter(
                ContentPost.id == post_id
            ).first()
            if not post:
                return False
            post.status    = "posted"
            post.posted_at = datetime.now(timezone.utc)
            if note:
                post.tweet_id = note
            db.commit()
        log.info(f"Post {post_id} marked as posted")
        return True
    except Exception as e:
        log.error(f"mark_as_posted error: {e}")
        return False


def get_posting_stats() -> dict:
    try:
        with SessionLocal() as db:
            posts = db.query(ContentPost).all()

        total     = len(posts)
        pending   = sum(1 for p in posts if p.status == "pending")
        posted    = sum(1 for p in posts if p.status == "posted")
        discarded = sum(1 for p in posts if p.status == "discarded")
        signals   = sum(1 for p in posts if p.signal_id is not None and p.status == "posted")
        commentary = sum(1 for p in posts if p.signal_id is None and p.status == "posted")

        return {
            "total":             total,
            "pending":           pending,
            "posted":            posted,
            "signal_posts":      signals,
            "commentary_posts":  commentary,
            "discarded":         discarded,
        }

    except Exception as e:
        log.error(f"Posting stats error: {e}")
        return {}