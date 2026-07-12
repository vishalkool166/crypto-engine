import logging
from alerts.telegram.client     import send
from alerts.telegram.formatters import now_ist
from config import cfg

log = logging.getLogger(__name__)


async def cmd_brief() -> None:
    await send("⏳ Generating market brief...")
    try:
        from data.fetcher import get_fear_greed
        from data.cache import cache
        from engines.state import get as get_coin_state
        from datetime import datetime, timezone

        fg = {"value": 50, "label": "Neutral"}
        try:
            fg = await get_fear_greed()
        except Exception:
            pass

        hour = datetime.now(timezone.utc).hour

        top_coins = []
        for coin in cfg.COINS[:8]:
            cached = cache.get_raw(f"signal_{coin}")
            if cached and cached.get("grade") not in ("--", None, "F"):
                top_coins.append({
                    "coin":  coin,
                    "grade": cached.get("grade", "--"),
                    "score": cached.get("score", 0),
                })
        top_coins = sorted(
            top_coins,
            key     = lambda x: x.get("score", 0),
            reverse = True,
        )[:3]

        btc_cached = cache.get_raw("signal_BTC")
        btc_change = 0.0
        if btc_cached:
            btc_change = btc_cached.get("market", {}).get("change24", 0)

        regimes = [
            cache.get_raw(f"signal_{c}").get("regime", "")
            for c in cfg.COINS
            if cache.get_raw(f"signal_{c}")
        ]
        regime = max(set(regimes), key=regimes.count) if regimes else "Unknown"

        sessions = [
            cache.get_raw(f"signal_{c}").get("session", "")
            for c in cfg.COINS
            if cache.get_raw(f"signal_{c}")
        ]
        session = sessions[0] if sessions else "Unknown"

        context = {
            "fg_val":     fg.get("value", 50),
            "fg_label":   fg.get("label", "Neutral"),
            "top_coins":  top_coins,
            "btc_change": btc_change,
            "regime":     regime,
            "session":    session,
            "time_label": (
                "Morning" if hour < 12
                else "Evening" if hour >= 17
                else "Midday"
            ),
        }

        from content.groq_writer import generate_brief_post
        draft = await generate_brief_post(context)
        if not draft:
            await send("❌ Brief generation failed.")
            return

        from content.approval_flow import send_brief_for_approval
        await send_brief_for_approval(draft)

    except Exception as e:
        log.error("cmd_brief error: %s", e)
        await send(f"❌ Brief failed: `{e}`")


async def cmd_pending() -> None:
    from content.approval_flow import get_pending_posts
    posts = await get_pending_posts()
    if not posts:
        await send(
            "📋 *Pending Posts*\n\n"
            "No posts waiting.\n\n"
            "Use /brief to generate a market post."
        )
        return
    lines = [f"📋 *Pending Posts — {len(posts)}*\n", "_Reply `#N` to see full text_\n"]
    for p in posts:
        pt      = p.get("post_type", "signal")
        icon    = "📊" if pt == "signal" else "💬"
        preview = p.get("post", "")[:80] + ("..." if len(p.get("post", "")) > 80 else "")
        coin_str = (
            f" — `{p.get('coin', 'MARKET')}USDT {p.get('direction', '--')}` Grade `{p.get('grade', '--')}`"
            if pt == "signal"
            else " — Market Commentary"
        )
        lines.append(
            f"{icon} *#{p['post_id']}*{coin_str}\n"
            f"_{preview}_\n"
        )
    lines.append("_Use `/discard N` to delete_")
    await send("\n".join(lines))


async def cmd_show_post(post_id: int) -> None:
    from content.approval_flow import get_post_text
    text = await get_post_text(post_id)
    if not text:
        await send(f"⚠️ Post #{post_id} not found.")
        return
    char_count = len(text)
    await send(
        f"📝 *Post #{post_id}* {'✅' if char_count <= 270 else '⚠️'} `{char_count}/270`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n{text}\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"_Copy and post manually._\n_Use `/discard {post_id}` to delete._"
    )


async def cmd_discard(post_id: int) -> None:
    from content.approval_flow import discard_post
    success = await discard_post(post_id)
    await send(
        f"🗑️ Post #{post_id} deleted."
        if success else
        f"⚠️ Post #{post_id} not found."
    )