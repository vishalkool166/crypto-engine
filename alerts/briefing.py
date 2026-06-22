import logging
from datetime import datetime, timezone, timedelta
from data.cache import cache
from config import cfg

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


async def send_morning_briefing():
    try:
        from alerts.telegram import send
        from content.groq_writer import generate_brief_post
        from content.approval_flow import send_brief_for_approval
        from data.fetcher import get_fear_greed

        fg = {"value": 50, "label": "Neutral"}
        try:
            fg = await get_fear_greed()
        except Exception:
            pass

        cached_results = []
        for coin in cfg.COINS:
            cached = cache.get_raw(f"signal_{coin}")
            if cached:
                cached_results.append(cached)

        cached_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        top_coins = []
        for r in cached_results[:3]:
            top_coins.append({
                "coin":  r.get("coin", "--"),
                "grade": r.get("grade", "F"),
                "score": r.get("score", 0)
            })

        btc_cached = cache.get_raw("signal_BTC")
        btc_change = 0.0
        if btc_cached:
            btc_change = btc_cached.get("market", {}).get("change24", 0)

        regimes = [r.get("regime", "") for r in cached_results if r.get("regime")]
        regime  = max(set(regimes), key=regimes.count) if regimes else "Unknown"

        sessions = [r.get("session", "") for r in cached_results if r.get("session")]
        session  = sessions[0] if sessions else "Unknown"

        context = {
            "regime":     regime,
            "session":    session,
            "fg_val":     fg.get("value", 50),
            "fg_label":   fg.get("label", "Neutral"),
            "btc_change": btc_change,
            "top_coins":  top_coins,
            "time_label": "Morning"
        }

        draft = await generate_brief_post(context)

        if draft:
            await send_brief_for_approval(draft)
        else:
            log.warning("Morning brief generation failed")

        log.info("Morning briefing sent")

    except Exception as e:
        log.error(f"Morning briefing error: {e}")


async def send_evening_briefing():
    try:
        from alerts.telegram import send
        from content.groq_writer import generate_brief_post
        from content.approval_flow import send_brief_for_approval
        from data.fetcher import get_fear_greed

        fg = {"value": 50, "label": "Neutral"}
        try:
            fg = await get_fear_greed()
        except Exception:
            pass

        cached_results = []
        for coin in cfg.COINS:
            cached = cache.get_raw(f"signal_{coin}")
            if cached:
                cached_results.append(cached)

        cached_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        top_coins = []
        for r in cached_results[:3]:
            top_coins.append({
                "coin":  r.get("coin", "--"),
                "grade": r.get("grade", "F"),
                "score": r.get("score", 0)
            })

        btc_cached = cache.get_raw("signal_BTC")
        btc_change = 0.0
        if btc_cached:
            btc_change = btc_cached.get("market", {}).get("change24", 0)

        regimes = [r.get("regime", "") for r in cached_results if r.get("regime")]
        regime  = max(set(regimes), key=regimes.count) if regimes else "Unknown"

        sessions = [r.get("session", "") for r in cached_results if r.get("session")]
        session  = sessions[0] if sessions else "Unknown"

        context = {
            "regime":     regime,
            "session":    session,
            "fg_val":     fg.get("value", 50),
            "fg_label":   fg.get("label", "Neutral"),
            "btc_change": btc_change,
            "top_coins":  top_coins,
            "time_label": "Evening"
        }

        draft = await generate_brief_post(context)

        if draft:
            await send_brief_for_approval(draft)
        else:
            log.warning("Evening brief generation failed")

        log.info("Evening briefing sent")

    except Exception as e:
        log.error(f"Evening briefing error: {e}")