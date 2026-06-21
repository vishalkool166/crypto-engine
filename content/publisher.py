import logging
import json
from datetime import datetime, timezone
from database import SessionLocal, ContentPost

log = logging.getLogger(__name__)


async def post_to_twitter(
    post_id:    int,
    text:       str,
    chart_path: str | None = None
) -> dict:
    """
    Post to Twitter/X using tweepy.
    Returns dict with success, tweet_id, url.
    """
    try:
        import tweepy
        from config import cfg

        if not all([
            cfg.TWITTER_API_KEY,
            cfg.TWITTER_API_SECRET,
            cfg.TWITTER_ACCESS_TOKEN,
            cfg.TWITTER_ACCESS_SECRET
        ]):
            return {"success": False, "reason": "Twitter API keys not configured"}

        # Twitter v2 client
        client = tweepy.Client(
            consumer_key        = cfg.TWITTER_API_KEY,
            consumer_secret     = cfg.TWITTER_API_SECRET,
            access_token        = cfg.TWITTER_ACCESS_TOKEN,
            access_token_secret = cfg.TWITTER_ACCESS_SECRET,
            wait_on_rate_limit  = True
        )

        media_id = None

        # Upload chart image if available
        if chart_path:
            try:
                import os
                if os.path.exists(chart_path):
                    # v1 API needed for media upload
                    auth = tweepy.OAuth1UserHandler(
                        consumer_key        = cfg.TWITTER_API_KEY,
                        consumer_secret     = cfg.TWITTER_API_SECRET,
                        access_token        = cfg.TWITTER_ACCESS_TOKEN,
                        access_token_secret = cfg.TWITTER_ACCESS_SECRET
                    )
                    api_v1   = tweepy.API(auth)
                    media    = api_v1.media_upload(filename=chart_path)
                    media_id = media.media_id_string
                    log.info(f"Chart uploaded to Twitter: media_id={media_id}")
            except Exception as e:
                log.warning(f"Chart upload failed — posting text only: {e}")
                media_id = None

        # Post tweet
        if media_id:
            response = client.create_tweet(
                text     = text,
                media_ids = [media_id]
            )
        else:
            response = client.create_tweet(text=text)

        tweet_id = str(response.data["id"])
        tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"

        # Update DB
        with SessionLocal() as db:
            post = db.query(ContentPost).filter(
                ContentPost.id == post_id
            ).first()
            if post:
                post.status    = "posted"
                post.tweet_id  = tweet_id
                post.posted_at = datetime.now(timezone.utc)
                db.commit()

        log.info(f"Tweet posted: {tweet_url}")

        return {
            "success":   True,
            "tweet_id":  tweet_id,
            "tweet_url": tweet_url
        }

    except Exception as e:
        log.error(f"Twitter post error: {e}")

        # Update DB to failed
        try:
            with SessionLocal() as db:
                post = db.query(ContentPost).filter(
                    ContentPost.id == post_id
                ).first()
                if post:
                    post.status = "failed"
                    db.commit()
        except Exception:
            pass

        return {"success": False, "reason": str(e)}


async def update_engagement(post_id: int) -> dict:
    """
    Fetch tweet engagement metrics and update DB.
    Returns engagement dict.
    """
    try:
        import tweepy
        from config import cfg

        with SessionLocal() as db:
            post = db.query(ContentPost).filter(
                ContentPost.id == post_id
            ).first()
            if not post or not post.tweet_id:
                return {}
            tweet_id = post.tweet_id

        client = tweepy.Client(
            consumer_key        = cfg.TWITTER_API_KEY,
            consumer_secret     = cfg.TWITTER_API_SECRET,
            access_token        = cfg.TWITTER_ACCESS_TOKEN,
            access_token_secret = cfg.TWITTER_ACCESS_SECRET,
            wait_on_rate_limit  = True
        )

        tweet = client.get_tweet(
            tweet_id,
            tweet_fields = ["public_metrics"]
        )

        if not tweet.data:
            return {}

        metrics = tweet.data.get("public_metrics", {})
        engagement = {
            "likes":    metrics.get("like_count",     0),
            "retweets": metrics.get("retweet_count",  0),
            "replies":  metrics.get("reply_count",    0),
            "views":    metrics.get("impression_count", 0),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        with SessionLocal() as db:
            post = db.query(ContentPost).filter(
                ContentPost.id == post_id
            ).first()
            if post:
                post.engagement_json = json.dumps(engagement)
                db.commit()

        log.info(f"Engagement updated post {post_id}: {engagement}")
        return engagement

    except Exception as e:
        log.error(f"Engagement update error post {post_id}: {e}")
        return {}


async def update_all_engagement():
    """Update engagement for all posted tweets."""
    try:
        with SessionLocal() as db:
            posts = db.query(ContentPost).filter(
                ContentPost.status   == "posted",
                ContentPost.tweet_id.isnot(None)
            ).all()
            post_ids = [p.id for p in posts]

        for post_id in post_ids:
            try:
                await update_engagement(post_id)
            except Exception as e:
                log.error(f"Engagement update failed post {post_id}: {e}")

        log.info(f"Engagement updated for {len(post_ids)} posts")

    except Exception as e:
        log.error(f"update_all_engagement error: {e}")


def get_posting_stats() -> dict:
    """Get overall posting statistics."""
    try:
        with SessionLocal() as db:
            posts = db.query(ContentPost).all()

        total     = len(posts)
        pending   = sum(1 for p in posts if p.status == "pending")
        posted    = sum(1 for p in posts if p.status == "posted")
        discarded = sum(1 for p in posts if p.status == "discarded")
        failed    = sum(1 for p in posts if p.status == "failed")

        total_likes    = 0
        total_retweets = 0
        total_views    = 0

        for p in posts:
            if p.engagement_json:
                try:
                    eng = json.loads(p.engagement_json)
                    total_likes    += eng.get("likes",    0)
                    total_retweets += eng.get("retweets", 0)
                    total_views    += eng.get("views",    0)
                except Exception:
                    pass

        return {
            "total":          total,
            "pending":        pending,
            "posted":         posted,
            "discarded":      discarded,
            "failed":         failed,
            "total_likes":    total_likes,
            "total_retweets": total_retweets,
            "total_views":    total_views,
            "avg_likes":      round(total_likes    / posted, 1) if posted > 0 else 0,
            "avg_retweets":   round(total_retweets / posted, 1) if posted > 0 else 0,
            "avg_views":      round(total_views    / posted, 1) if posted > 0 else 0,
        }

    except Exception as e:
        log.error(f"Posting stats error: {e}")
        return {}