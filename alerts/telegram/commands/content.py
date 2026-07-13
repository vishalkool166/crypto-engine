import logging
from alerts.telegram.client import send
from config import cfg

log = logging.getLogger(__name__)


async def cmd_brief() -> None:
    from datetime import datetime, timezone, timedelta
    from data.cache import cache
    from data.fetcher import get_fear_greed
    from trade.ws import get_mark_price, get_binance_account
    from alerts.scanner import get_db_stats
    from scheduler import get_next_scan_time

    await send("⏳ Generating market report...")

    try:
        IST  = timezone(timedelta(hours=5, minutes=30))
        now  = datetime.now(IST)
        hour = datetime.now(timezone.utc).hour

        if 8  <= hour < 13:  session = "London"
        elif 13 <= hour < 17: session = "London/NY Overlap"
        elif 17 <= hour < 21: session = "New York"
        elif 0  <= hour < 8:  session = "Asia"
        else:                  session = "Off Hours"

        time_label = now.strftime("%d %b %Y · %I:%M %p IST")

        fg = {"value": 50, "label": "Neutral"}
        try:
            fg = await get_fear_greed()
        except Exception:
            pass

        fg_val   = fg.get("value", 50)
        fg_label = fg.get("label", "Neutral")
        fg_emoji = "🟢" if fg_val >= 60 else "🔴" if fg_val <= 30 else "🟡"

        btc_cached = cache.get_raw("signal_BTC")
        btc_price  = 0.0
        btc_change = 0.0
        btc_dir    = "Neutral"
        btc_adx    = 0.0

        if btc_cached:
            btc_price  = btc_cached.get("market", {}).get("price",    0)
            btc_change = btc_cached.get("market", {}).get("change24", 0)

        btc_data = cache.get_raw("btc_4h_data")
        if btc_data:
            btc_dir = btc_data.get("trend", {}).get("label", "Neutral")
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

        regime_rec = "Normal conditions"
        if "chop" in dominant_regime.lower():
            regime_rec = "⚠️ Choppy — reduce size"
        elif "rang" in dominant_regime.lower():
            regime_rec = "⚠️ Ranging — tighter management"
        elif "bear" in dominant_regime.lower():
            regime_rec = "📉 Bearish trend — prefer shorts"
        elif "bull" in dominant_regime.lower():
            regime_rec = "📈 Bullish trend — prefer longs"

        all_cached = []
        for coin in cfg.COINS:
            c = cache.get_raw(f"signal_{coin}")
            if c:
                all_cached.append(c)

        tradeable = [
            r for r in all_cached
            if r.get("grade") in ("A+", "A", "B")
            and r.get("direction") in ("LONG", "SHORT")
            and r.get("score", 0) > 0
        ]
        tradeable.sort(key=lambda x: x.get("score", 0), reverse=True)

        watching = [
            r for r in all_cached
            if r.get("state") == "watching"
            and r.get("grade") not in ("A+", "A", "B")
        ]

        from database import SessionLocal, Trade as TradeModel
        open_trades = []
        try:
            with SessionLocal() as db:
                trades = db.query(TradeModel).filter(
                    TradeModel.is_active == True
                ).all()
                for t in trades:
                    live = get_mark_price(t.coin) or float(t.entry_price or 0)
                    entry    = float(t.entry_price or 0)
                    margin   = float(t.margin_used or 0)
                    leverage = int(t.leverage or 1)
                    is_short = t.direction == "SHORT"
                    if entry > 0:
                        ratio   = (entry - live) / entry if is_short else (live - entry) / entry
                        pnl_abs = round(ratio * margin * leverage, 4)
                    else:
                        pnl_abs = 0.0
                    open_trades.append({
                        "coin":      t.coin,
                        "direction": t.direction,
                        "grade":     t.grade,
                        "entry":     entry,
                        "live":      live,
                        "pnl":       pnl_abs,
                        "tp1":       float(t.tp1_price or 0),
                        "sl":        float(t.sl_price  or 0),
                    })
        except Exception as e:
            log.error("cmd_brief open trades: %s", e)

        from datetime import date, timedelta as td
        stats_7d = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0}
        try:
            week_start = datetime.now(timezone.utc) - td(days=7)
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

        all_stats = get_db_stats()
        next_scan = get_next_scan_time()

        btc_sign   = "+" if btc_change >= 0 else ""
        eth_sign   = "+" if eth_change >= 0 else ""
        pnl_sign   = "+" if stats_7d["pnl"] >= 0 else ""
        wr_7d      = round(stats_7d["wins"] / stats_7d["trades"] * 100, 1) if stats_7d["trades"] > 0 else 0

        lines = [
            f"📊 *Market Report — {time_label}*",
            f"",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"*MARKET OVERVIEW*",
            f"━━━━━━━━━━━━━━━━━━━━━━",
        ]

        if btc_price:
            lines.append(f"BTC:  `${btc_price:,.2f}`  `{btc_sign}{btc_change:.2f}%`  {btc_dir} · ADX `{btc_adx:.0f}`")
        if eth_price:
            lines.append(f"ETH:  `${eth_price:,.2f}`  `{eth_sign}{eth_change:.2f}%`")

        lines += [
            f"{fg_emoji} Fear & Greed:  `{fg_val}/100 — {fg_label}`",
            f"",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"*REGIME & SESSION*",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"Dominant Regime:  `{dominant_regime}`",
            f"Current Session:  `{session}`",
            f"Recommendation:   {regime_rec}",
            f"",
        ]

        if tradeable:
            lines += [
                f"━━━━━━━━━━━━━━━━━━━━━━",
                f"*TOP SETUPS ({len(tradeable)})*",
                f"━━━━━━━━━━━━━━━━━━━━━━",
            ]
            for i, r in enumerate(tradeable[:5], 1):
                coin      = r.get("coin", "--")
                direction = r.get("direction", "--")
                grade     = r.get("grade", "--")
                score     = r.get("score", 0)
                state     = r.get("state", "--")
                sweep     = r.get("sweep", {})
                zone      = r.get("zone",  {})
                dir_emoji = "📈" if direction == "LONG" else "📉"

                line = f"{i}. {dir_emoji} *{coin}*  `{direction}`  Grade `{grade}`  Score `{score}/100`"
                lines.append(line)

                if zone.get("bottom") and zone.get("top"):
                    lines.append(f"   Zone: `{zone['bottom']:.4f} – {zone['top']:.4f}`")

                if sweep.get("detected") and sweep.get("age_hours"):
                    lines.append(f"   Sweep: `{sweep.get('label', '--')}` · `{sweep['age_hours']:.1f}h ago`")

                if state == "watching":
                    lines.append(f"   Status: ⚡ Watching — trigger pending")
                elif state in ("signal_ready",):
                    lines.append(f"   Status: 🎯 Signal ready")

                lines.append("")

        elif watching:
            lines += [
                f"━━━━━━━━━━━━━━━━━━━━━━",
                f"*WATCHING ZONES ({len(watching)})*",
                f"━━━━━━━━━━━━━━━━━━━━━━",
            ]
            for r in watching[:3]:
                coin      = r.get("coin", "--")
                direction = r.get("direction", "--")
                zone      = r.get("zone", {})
                dir_emoji = "📈" if direction == "LONG" else "📉"
                lines.append(f"{dir_emoji} `{coin}` — `{direction}`")
                if zone.get("distance_pct"):
                    lines.append(f"   `{zone['distance_pct']:.2f}%` from zone")
                lines.append("")
        else:
            lines += [
                f"━━━━━━━━━━━━━━━━━━━━━━",
                f"*SETUPS*",
                f"━━━━━━━━━━━━━━━━━━━━━━",
                f"No active setups — scanning",
                f"",
            ]

        lines += [
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"*OPEN TRADES*",
            f"━━━━━━━━━━━━━━━━━━━━━━",
        ]

        if open_trades:
            for t in open_trades:
                pnl_str   = f"+${t['pnl']:.4f}" if t["pnl"] >= 0 else f"-${abs(t['pnl']):.4f}"
                pnl_emoji = "🟢" if t["pnl"] >= 0 else "🔴"
                dir_emoji = "📈" if t["direction"] == "LONG" else "📉"
                lines.append(
                    f"{dir_emoji} *{t['coin']}* `{t['direction']}` Grade `{t['grade']}`"
                )
                lines.append(
                    f"   Entry `{t['entry']:.4f}` · Live `{t['live']:.4f}` · {pnl_emoji} `{pnl_str}`"
                )
                if t["tp1"] and t["sl"]:
                    lines.append(f"   TP `{t['tp1']:.4f}` · SL `{t['sl']:.4f}`")
                lines.append("")
        else:
            lines.append("No open trades")
            lines.append("")

        lines += [
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"*PERFORMANCE (Last 7 days)*",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"Trades:   `{stats_7d['trades']}`  ·  Wins: `{stats_7d['wins']}`  ·  Losses: `{stats_7d['losses']}`",
            f"Win Rate: `{wr_7d}%`",
            f"PnL:      `{pnl_sign}${stats_7d['pnl']:.4f}`",
            f"",
            f"*All-time:*  `{all_stats.get('closed', 0)}` trades  ·  `{all_stats.get('win_rate', 0)}%` WR  ·  `${all_stats.get('total_pnl', 0):.2f}` PnL",
            f"",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"Next scan: `{next_scan}`",
            f"Mode: `{'🔴 LIVE' if not cfg.PAPER_TRADING else '🔵 PAPER'}`  ·  Version: `{cfg.SYSTEM_VERSION}`",
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
            "📋 *Pending Posts*\n\n"
            "No posts waiting.\n\n"
            "Posts are generated automatically when A+/A signals fire."
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