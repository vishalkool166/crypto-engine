import logging
from alerts.telegram.client import send
from config import cfg

log = logging.getLogger(__name__)

IST_OFFSET = 5.5


def _now_ist() -> str:
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%I:%M %p IST")


def _now_ist_full() -> str:
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d %b %Y · %I:%M %p IST")


async def cmd_brief() -> None:
    from datetime import datetime, timezone, timedelta, date as _date
    from data.cache import cache
    from data.fetcher import get_fear_greed
    from alerts.scanner import get_db_stats
    from scheduler import get_next_scan_time
    from trade.monitor import get_open_positions_enriched

    await send("⏳ Generating market report...")

    try:
        IST  = timezone(timedelta(hours=5, minutes=30))
        now  = datetime.now(IST)
        hour = datetime.now(timezone.utc).hour

        if   8  <= hour < 13: session = "London"
        elif 13 <= hour < 17: session = "London/NY Overlap"
        elif 17 <= hour < 21: session = "New York"
        elif 0  <= hour < 8:  session = "Asia"
        else:                  session = "Off Hours"

        session_emoji = {
            "London/NY Overlap": "🟢",
            "London":            "🟡",
            "New York":          "🟡",
            "Asia":              "🔵",
            "Off Hours":         "⚫",
        }.get(session, "⚫")

        fg = {"value": 50, "label": "Neutral", "stale": False}
        try:
            fg = await get_fear_greed()
        except Exception:
            pass

        fg_val   = fg.get("value", 50)
        fg_label = fg.get("label", "Neutral")
        fg_emoji = "🤑" if fg_val >= 75 else "😊" if fg_val >= 55 else "😐" if fg_val >= 45 else "😰" if fg_val >= 25 else "😱"

        btc_cached = cache.get_raw("signal_BTC")
        btc_price  = 0.0
        btc_change = 0.0
        btc_adx    = 0.0

        if btc_cached:
            btc_price  = btc_cached.get("market", {}).get("price",    0)
            btc_change = btc_cached.get("market", {}).get("change24", 0)

        btc_data = cache.get_raw("btc_4h_data")
        if btc_data:
            btc_adx = float(btc_data.get("adx") or 0)

        eth_cached = cache.get_raw("signal_ETH")
        eth_price  = 0.0
        eth_change = 0.0
        if eth_cached:
            eth_price  = eth_cached.get("market", {}).get("price",    0)
            eth_change = eth_cached.get("market", {}).get("change24", 0)

        regimes = []
        for coin in cfg.COINS:
            c = cache.get_raw(f"signal_{coin}")
            if c and c.get("regime"):
                regimes.append(c["regime"])

        dominant_regime = max(set(regimes), key=regimes.count) if regimes else "Unknown"

        regime_emoji = "📈" if "bull" in dominant_regime.lower() or "trend" in dominant_regime.lower() else "📉" if "bear" in dominant_regime.lower() else "↔️"

        all_cached = []
        for coin in cfg.COINS:
            c = cache.get_raw(f"signal_{coin}")
            if c:
                all_cached.append(c)

        live_signals = [
            r for r in all_cached
            if r.get("grade") in ("A+", "A", "B")
            and r.get("direction") in ("LONG", "SHORT")
            and r.get("score", 0) > 0
        ]
        live_signals.sort(key=lambda x: x.get("score", 0), reverse=True)

        watching = [
            r for r in all_cached
            if r.get("state") == "watching"
            and r.get("grade") not in ("A+", "A", "B")
        ]

        open_trades = await get_open_positions_enriched()
        all_stats   = get_db_stats()
        next_scan   = get_next_scan_time()
        mode        = "🔴 LIVE" if not cfg.PAPER_TRADING else "🔵 PAPER"

        btc_sign = "+" if btc_change >= 0 else ""
        eth_sign = "+" if eth_change >= 0 else ""

        lines = [
            f"📊 *Market Report*\n"
            f"🕐 `{_now_ist_full()}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*Market Overview*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
        ]

        if btc_price:
            lines.append(f"₿ BTC:  `${btc_price:,.2f}`  `{btc_sign}{btc_change:.2f}%`  ADX `{btc_adx:.0f}`")
        if eth_price:
            lines.append(f"Ξ ETH:  `${eth_price:,.2f}`  `{eth_sign}{eth_change:.2f}%`")

        lines += [
            f"{fg_emoji} F&G:   `{fg_val}/100 — {fg_label}`\n",
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*Regime & Session*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{regime_emoji} Regime:   `{dominant_regime}`\n"
            f"{session_emoji} Session:  `{session}`\n",
        ]

        if live_signals:
            lines.append(
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"*🎯 Active Signals — {len(live_signals)}*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )
            for i, r in enumerate(live_signals[:5], 1):
                coin      = r.get("coin",      "--")
                direction = r.get("direction", "--")
                grade     = r.get("grade",     "--")
                score     = r.get("score",     0)
                signal    = r.get("signal",    {})
                entry     = signal.get("entry")
                g_emoji   = {"A+": "🏆", "A": "⭐", "B": "👀"}.get(grade, "📊")
                d_emoji   = "📈" if direction == "LONG" else "📉"

                line = f"{i}. {g_emoji} *{coin}*  {d_emoji} `{direction}`  Score `{score}`"
                lines.append(line)

                if entry:
                    sl  = signal.get("sl")
                    tp1 = signal.get("tp1")
                    lines.append(f"   🎯 `{entry:.4f}`  🛑 `{sl:.4f}`  ✅ `{tp1:.4f}`")
                lines.append("")

        elif watching:
            lines.append(
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"*⚡ Watching — {len(watching)}*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )
            for r in watching[:3]:
                coin      = r.get("coin",      "--")
                direction = r.get("direction", "--")
                score     = r.get("score",     0)
                d_emoji   = "📈" if direction == "LONG" else "📉" if direction == "SHORT" else "➖"
                lines.append(f"  {d_emoji} `{coin}`  Score `{score}`")
            lines.append("")
        else:
            lines.append(
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"*Signals*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"😴 No active setups — scanning\n"
            )

        lines.append(
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*Open Trades*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )

        if open_trades:
            for t in open_trades:
                coin      = t.get("coin",      "--")
                direction = t.get("direction", "--")
                grade     = t.get("grade",     "--")
                entry     = float(t.get("entry_price")   or 0)
                live      = float(t.get("current_price") or entry)
                pnl_abs   = float(t.get("profit_abs")    or 0)
                pnl_str   = f"+${pnl_abs:.4f}" if pnl_abs >= 0 else f"-${abs(pnl_abs):.4f}"
                pnl_emoji = "💚" if pnl_abs >= 0 else "🔴"
                d_emoji   = "📈" if direction == "LONG" else "📉"
                g_emoji   = {"A+": "🏆", "A": "⭐", "B": "👀"}.get(grade, "📊")

                lines.append(
                    f"{d_emoji} *{coin}* {g_emoji} `{grade}`\n"
                    f"   Entry `{entry:.4f}` · Live `{live:.4f}` · {pnl_emoji} `{pnl_str}`"
                )
        else:
            lines.append("😴 No open trades")

        stats_7d = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0}
        try:
            from database import SessionLocal, Trade as TradeModel
            week_start = datetime.now(timezone.utc) - timedelta(days=7)
            with SessionLocal() as db:
                recent = db.query(TradeModel).filter(
                    TradeModel.closed_at >= week_start,
                    TradeModel.outcome.in_(["win", "loss"])
                ).all()
                stats_7d["trades"]  = len(recent)
                stats_7d["wins"]    = sum(1 for t in recent if t.outcome == "win")
                stats_7d["losses"]  = sum(1 for t in recent if t.outcome == "loss")
                stats_7d["pnl"]     = round(sum(float(t.binance_net_pnl or t.net_pnl or t.pnl or 0) for t in recent), 4)
        except Exception as e:
            log.error("cmd_brief 7d stats: %s", e)

        wr_7d     = round(stats_7d["wins"] / stats_7d["trades"] * 100, 1) if stats_7d["trades"] > 0 else 0
        pnl_7d    = stats_7d["pnl"]
        pnl_sign  = "+" if pnl_7d >= 0 else ""
        pnl_emoji = "💚" if pnl_7d >= 0 else "🔴"

        all_pnl   = all_stats.get("total_pnl", 0)
        all_sign  = "+" if all_pnl >= 0 else ""

        lines += [
            f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*Performance (7 days)*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Trades:    `{stats_7d['trades']}`  ✅ `{stats_7d['wins']}`  ❌ `{stats_7d['losses']}`\n"
            f"🎯 Win Rate:  `{wr_7d}%`\n"
            f"{pnl_emoji} PnL:       `{pnl_sign}${pnl_7d:.4f}`\n\n"
            f"*All Time:*  `{all_stats.get('closed', 0)}` trades  ·  `{all_stats.get('win_rate', 0)}%` WR  ·  `{all_sign}${all_pnl:.2f}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 Next scan: `{next_scan}`\n"
            f"{mode}  ·  v`{cfg.SYSTEM_VERSION}`"
        ]

        await send("\n".join(lines))

    except Exception as e:
        log.error("cmd_brief error: %s", e)
        await send(f"❌ Report failed: `{e}`")


async def cmd_pending() -> None:
    from content.approval_flow import get_pending_posts

    posts = await get_pending_posts()
    if not posts:
        await send(
            f"📋 *Pending Posts*\n\n"
            f"✅ No posts waiting.\n\n"
            f"_Posts are generated automatically when A+/A signals fire._"
        )
        return

    lines = [
        f"📋 *Pending Posts — {len(posts)}*\n"
        f"_Reply `#N` to see full text_\n"
    ]

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
    status     = "✅" if char_count <= 270 else "⚠️"

    await send(
        f"📝 *Post #{post_id}* {status} `{char_count}/270`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"_Copy and post manually._\n"
        f"_Use `/discard {post_id}` to delete._"
    )


async def cmd_discard(post_id: int) -> None:
    from content.approval_flow import discard_post

    success = await discard_post(post_id)
    await send(
        f"🗑️ Post #{post_id} deleted."
        if success else
        f"⚠️ Post #{post_id} not found."
    )