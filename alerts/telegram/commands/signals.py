import logging
from alerts.telegram.client     import send
from alerts.telegram.formatters import now_ist, all_cached_signals
from config import cfg

log = logging.getLogger(__name__)


async def cmd_coin(coin: str) -> None:
    from engines.state import get as get_coin_state
    from trade.ws import get_mark_price

    coin_state = get_coin_state(coin)
    status     = coin_state["status"]
    setup      = coin_state.get("setup") or {}
    direction  = setup.get("direction", "--")
    zone       = setup.get("zone",  {}) or {}
    sweep      = setup.get("sweep", {}) or {}
    live       = get_mark_price(coin) or 0

    state_emoji = {
        "idle":     "😴",
        "watching": "⚡",
        "in_trade": "🔥",
        "cooldown": "⏳",
    }.get(status, "❓")

    dir_emoji = "📈" if direction == "LONG" else "📉" if direction == "SHORT" else "➖"

    msg = (
        f"📊 *{coin}USDT*\n_{now_ist()}_\n\n"
        f"Price:     `${live:,.4f}`\n"
        f"State:     {state_emoji} `{status.upper()}`\n"
        f"Direction: {dir_emoji} `{direction}`\n"
    )

    if sweep and sweep.get("detected"):
        msg += (
            f"\n*Sweep:*\n"
            f"Label:     `{sweep.get('label', '--')}`\n"
            f"Age:       `{sweep.get('age_hours', 0):.1f}h ago`\n"
            f"Score:     `{sweep.get('score', 0):.2f}`\n"
        )

    if zone and zone.get("type"):
        msg += (
            f"\n*Zone:*\n"
            f"Type:      `{zone.get('type', '--')}`\n"
            f"Range:     `{zone.get('bottom', 0):.4f} - {zone.get('top', 0):.4f}`\n"
            f"Distance:  `{zone.get('distance_pct', 0):.2f}%`\n"
            f"Touches:   `{zone.get('touch_count', 0)}`\n"
        )

    await send(msg)


async def cmd_btc() -> None:
    await cmd_coin("BTC")


async def cmd_funding() -> None:
    lines = [f"💸 *Funding Rates*\n_{now_ist()}_\n"]
    for c in all_cached_signals():
        coin    = c.get("coin", "")
        funding = c.get("market", {}).get("funding", 0) * 100
        flag    = "🚨" if abs(funding) > 0.08 else "⚠️" if abs(funding) > 0.05 else "✅"
        lines.append(f"{flag} `{coin}` — `{funding:.4f}%`")
    if len(lines) == 1:
        lines.append("No data — run /scan first")
    await send("\n".join(lines))


async def cmd_fear() -> None:
    from data.fetcher import get_fear_greed
    try:
        fg    = await get_fear_greed()
        val   = fg.get("value", 50)
        emoji = "🟢" if val >= 60 else "🔴" if val <= 30 else "🟡"
        await send(
            f"{emoji} *Fear & Greed Index*\n_{now_ist()}_\n\n"
            f"Value: `{val}/100`\nLabel: `{fg.get('label', 'Neutral')}`\n"
            f"{'⚠️ _Stale data_' if fg.get('stale') else ''}"
        )
    except Exception as e:
        await send(f"❌ Fear & Greed failed: `{e}`")