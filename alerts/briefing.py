import logging
from datetime import datetime, timezone, timedelta
from data.cache import cache
from config import cfg
from database import SessionLocal, Trade, Signal as SignalModel
from trade.state import state_manager
from trade.risk import risk_guard

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist_str() -> str:
    return datetime.now(IST).strftime("%d %b · %I:%M %p IST")


async def send_morning_briefing():
    from alerts.telegram import send
    from data.fetcher import get_fear_greed

    try:
        fg = await get_fear_greed()
    except Exception:
        fg = {"value": 50, "label": "Neutral"}

    # Collect cached scan results
    cached_results = []
    for coin in cfg.COINS:
        cached = cache.get(f"signal_{coin}")
        if cached:
            cached_results.append(cached)

    cached_results.sort(key=lambda x: x.get("score", 0), reverse=True)

    # BTC context
    btc_cached = cache.get("signal_BTC")
    btc_line   = ""
    if btc_cached:
        btc_market = btc_cached.get("market", {})
        btc_change = btc_market.get("change24", 0)
        btc_regime = btc_cached.get("regime", "--")
        sign       = "+" if btc_change >= 0 else ""
        btc_line   = f"BTC: `{sign}{btc_change:.2f}%` overnight — `{btc_regime}`\n"

    # Fear & greed
    fg_val   = fg.get("value", 50)
    fg_label = fg.get("label", "Neutral")
    fg_emoji = (
        "🟢" if fg_val >= 60 else
        "🔴" if fg_val <= 30 else
        "🟡"
    )

    # Top setups
    tradeable = [
        r for r in cached_results
        if r.get("grade") in ["A+", "A"] and
        r.get("direction") in ["LONG", "SHORT"]
    ]
    watching = [
        r for r in cached_results
        if r.get("grade") == "B" and
        r.get("direction") in ["LONG", "SHORT"]
    ]
    building = [
        r for r in cached_results
        if r.get("grade") == "C"
    ]

    setups_lines = []
    if tradeable:
        setups_lines.append("*Tradeable Now:*")
        for r in tradeable[:3]:
            g   = r.get("grade", "?")
            d   = r.get("direction", "?")
            s   = r.get("score", 0)
            em  = "📈" if d == "LONG" else "📉"
            setups_lines.append(
                f"{em} `{r['coin']}` — Grade {g} ({s}/100)"
            )
    if watching:
        setups_lines.append("\n*Watching:*")
        for r in watching[:3]:
            d  = r.get("direction", "?")
            s  = r.get("score", 0)
            em = "📈" if d == "LONG" else "📉"
            expl   = r.get("explanation", {})
            reason = expl.get("no_trade_reason", "")
            short  = reason.split("\n")[2].strip() if reason and len(reason.split("\n")) > 2 else "setup building"
            setups_lines.append(
                f"{em} `{r['coin']}` — B ({s}/100) — {short}"
            )
    if building and not tradeable and not watching:
        setups_lines.append("\n*Building:*")
        for r in building[:2]:
            setups_lines.append(
                f"👁 `{r['coin']}` — C ({r.get('score',0)}/100)"
            )

    if not setups_lines:
        setups_lines.append("No setups in cache — trigger /scan for fresh data")

    # Daily risk
    risk_stats  = risk_guard.get_daily_stats()
    trades_left = risk_stats.get("remaining_trades", cfg.MAX_TRADES_PER_DAY)
    loss_left   = risk_stats.get("remaining_loss", cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT)

    # Active trade context
    trade_line = ""
    if not state_manager.is_idle:
        t = state_manager.current_trade
        if t:
            trade_line = (
                f"\n⚡ *Active Trade:* `{t.coin}USDT {t.direction}` "
                f"Grade `{t.grade}`\n"
            )

    await send(
        f"🌅 *Morning Briefing — {now_ist_str()}*\n\n"
        f"{btc_line}"
        f"{fg_emoji} Fear & Greed: `{fg_val} — {fg_label}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{chr(10).join(setups_lines)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*Today Risk*\n"
        f"Trades left: `{trades_left}/{cfg.MAX_TRADES_PER_DAY}`\n"
        f"Loss cap left: `${loss_left:.4f}`\n"
        f"{trade_line}\n"
        f"Next scan: next `:00/:15/:30/:45` UTC\n"
        f"Type /scan to scan now"
    )

    log.info("Morning briefing sent")


async def send_post_trade_debrief(
    trade,
    outcome:      str,
    pnl:          float,
    close_reason: str,
    health_at_close: str
):
    from alerts.telegram import send

    is_win  = outcome == "win"
    is_loss = outcome == "loss"

    result_emoji = "✅" if is_win else "❌" if is_loss else "⏹"
    pnl_str      = f"+${pnl:.4f}" if pnl >= 0 else f"-${abs(pnl):.4f}"

    # Pull signal data from cache for thesis context
    cached      = cache.get(f"signal_{trade.coin}")
    explanation = cached.get("explanation", {}) if cached else {}
    thesis      = explanation.get("thesis", "")
    risk_thesis = explanation.get("risk_thesis", "")

    # What worked / what to watch
    worked_lines  = []
    watch_lines   = []

    if thesis:
        for line in thesis.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("✔"):
                worked_lines.append(line)
            elif line.startswith("⚠"):
                watch_lines.append(line)

    if risk_thesis:
        for line in risk_thesis.split("\n"):
            line = line.strip()
            if line and line.startswith("⚠"):
                if line not in watch_lines:
                    watch_lines.append(line)

    worked_block = (
        "\n".join(worked_lines)
        if worked_lines
        else "No thesis data available"
    )
    watch_block = (
        "\n".join(watch_lines[:3])
        if watch_lines
        else "No risk flags at entry"
    )

    # Running grade accuracy
    grade_line = _get_grade_accuracy(trade.grade)

    # Health context
    health_emoji = (
        "✅" if health_at_close == "HEALTHY"     else
        "⚠️" if health_at_close == "WARNING"     else
        "🚨" if health_at_close == "INVALIDATED" else
        "—"
    )

    thesis_held = (
        "Thesis held from entry to exit" if health_at_close == "HEALTHY" else
        "Thesis weakened during trade"   if health_at_close == "WARNING" else
        "Thesis invalidated before close" if health_at_close == "INVALIDATED" else
        "--"
    )

    await send(
        f"📋 *Trade Debrief — {trade.coin}USDT {trade.direction}*\n\n"
        f"Result: {result_emoji} `{outcome.upper()}` — `{pnl_str}`\n"
        f"Reason: `{close_reason}`\n"
        f"Grade:  `{trade.grade}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*What Worked*\n{worked_block}\n\n"
        f"*Watch For Next Time*\n{watch_block}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Health at close: {health_emoji} `{health_at_close}`\n"
        f"{thesis_held}\n\n"
        f"{grade_line}\n"
        f"Type /pnl for full stats"
    )

    log.info(f"Post-trade debrief sent: {trade.coin} {outcome} ${pnl:.4f}")


def _get_grade_accuracy(grade: str) -> str:
    db = SessionLocal()
    try:
        trades = db.query(Trade).filter(
            Trade.grade    == grade,
            Trade.is_active == False,
            Trade.outcome.in_(["win", "loss"])
        ).all()

        if not trades:
            return f"Grade {grade} accuracy: no data yet"

        wins = len([t for t in trades if t.outcome == "win"])
        total = len(trades)
        wr    = round(wins / total * 100, 1)

        return (
            f"Grade {grade} accuracy: "
            f"`{wins}W {total - wins}L` — `{wr}% win rate`"
        )
    except Exception as e:
        log.error(f"Grade accuracy error: {e}")
        return ""
    finally:
        db.close()