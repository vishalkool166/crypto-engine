import logging
from alerts.telegram.client import send
from config import cfg

log = logging.getLogger(__name__)


def _now_ist() -> str:
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%I:%M %p IST")


def _grade_emoji(grade: str) -> str:
    return {"A+": "🏆", "A": "⭐", "B": "👀"}.get(grade, "📊")


def _dir_emoji(direction: str) -> str:
    return "📈" if direction == "LONG" else "📉" if direction == "SHORT" else "➖"


async def cmd_coin(coin: str) -> None:
    from data.cache import cache
    from trade.ws import get_mark_price
    from engines.state import get as get_coin_state

    cached     = cache.get_raw(f"signal_{coin}")
    live_price = get_mark_price(coin) or 0
    state      = get_coin_state(coin)
    status     = state.get("status", "idle")

    state_emoji = {
        "watching":  "⚡",
        "in_trade":  "🔥",
        "cooldown":  "💤",
        "idle":      "😴",
    }.get(status, "❓")

    if not cached:
        await send(
            f"📊 *{coin}USDT*\n"
            f"🕐 `{_now_ist()}`\n\n"
            f"💲 Price:   `${live_price:,.4f}`\n"
            f"{state_emoji} State:   `{status.upper()}`\n\n"
            f"_No scan data — run /scan first_"
        )
        return

    grade     = cached.get("grade",     "--")
    direction = cached.get("direction", "--")
    score     = cached.get("score",     0)
    regime    = cached.get("regime",    "--")
    reason    = cached.get("reason",    "")
    market    = cached.get("market",    {})
    signal    = cached.get("signal",    {})

    price     = live_price or market.get("price", 0)
    change    = market.get("change24", 0)
    funding   = market.get("funding",  0) * 100

    change_emoji = "📈" if change >= 0 else "📉"
    g_emoji      = _grade_emoji(grade)
    d_emoji      = _dir_emoji(direction)

    msg = (
        f"📊 *{coin}USDT*\n"
        f"🕐 `{_now_ist()}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💲 Price:    `${price:,.4f}`\n"
        f"{change_emoji} 24h:     `{'+' if change >= 0 else ''}{change:.2f}%`\n"
        f"💸 Funding:  `{funding:.4f}%`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{state_emoji} State:   `{status.upper()}`\n"
    )

    if grade != "--":
        msg += f"{g_emoji} Grade:   `{grade}`\n"

    if direction not in ("--", "NEUTRAL"):
        msg += f"{d_emoji} Dir:     `{direction}`\n"

    if score > 0:
        msg += f"🎯 Score:   `{score:.1f}`\n"

    if regime and regime not in ("--", "None", ""):
        msg += f"📍 Regime:  `{regime}`\n"

    if reason and grade == "--":
        msg += f"❌ Reason:  `{reason.replace('_', ' ')}`\n"

    if signal and signal.get("entry"):
        entry = signal.get("entry", 0)
        sl    = signal.get("sl",    0)
        tp1   = signal.get("tp1",   0)
        sl_pct= signal.get("sl_pct", 0)
        rr1   = signal.get("rr1",   0)
        msg += (
            f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Entry:   `{entry:.4f}`\n"
            f"🛑 SL:      `{sl:.4f}` ({sl_pct:.2f}%)\n"
            f"✅ TP:      `{tp1:.4f}` ({rr1:.1f}R)\n"
        )

    await send(msg)


async def cmd_btc() -> None:
    await cmd_coin("BTC")


async def cmd_funding() -> None:
    from data.cache import cache

    lines = [f"💸 *Funding Rates*\n🕐 `{_now_ist()}`\n"]

    coins_data = []
    for coin in cfg.COINS:
        c = cache.get_raw(f"signal_{coin}")
        if not c:
            continue
        funding = c.get("market", {}).get("funding", 0) * 100
        coins_data.append((coin, funding))

    if not coins_data:
        await send("💸 *Funding Rates*\n\n_No data — run /scan first_")
        return

    coins_data.sort(key=lambda x: abs(x[1]), reverse=True)

    for coin, funding in coins_data:
        if abs(funding) > 0.08:
            flag = "🚨"
        elif abs(funding) > 0.05:
            flag = "⚠️"
        else:
            flag = "✅"
        sign = "+" if funding >= 0 else ""
        lines.append(f"{flag} `{coin:<6}` `{sign}{funding:.4f}%`")

    await send("\n".join(lines))


async def cmd_fear() -> None:
    from data.fetcher import get_fear_greed

    try:
        fg    = await get_fear_greed()
        val   = fg.get("value", 50)
        label = fg.get("label", "Neutral")

        if val >= 75:
            emoji = "🤑"
            color = "Extreme Greed"
        elif val >= 55:
            emoji = "😊"
            color = "Greed"
        elif val >= 45:
            emoji = "😐"
            color = "Neutral"
        elif val >= 25:
            emoji = "😰"
            color = "Fear"
        else:
            emoji = "😱"
            color = "Extreme Fear"

        bar_filled = round(val / 10)
        bar        = "█" * bar_filled + "░" * (10 - bar_filled)

        stale_note = "\n⚠️ _Stale data_" if fg.get("stale") else ""

        await send(
            f"{emoji} *Fear & Greed Index*\n"
            f"🕐 `{_now_ist()}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"`{bar}`\n\n"
            f"📊 Value:  `{val}/100`\n"
            f"🏷️ Label:  `{label}`\n"
            f"📍 Zone:   `{color}`"
            f"{stale_note}"
        )
    except Exception as e:
        await send(f"❌ Fear & Greed failed: `{e}`")