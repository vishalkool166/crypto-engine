import logging
from datetime import datetime, timezone, timedelta
from data.cache import cache
from config import cfg
from database import SessionLocal, Trade, Signal as SignalModel
from trade.state import state_manager
from trade.risk import risk_guard
from alerts.utils import now_ist_str, grade_accuracy_str, categorize_results

log = logging.getLogger(__name__)


async def send_morning_briefing():
    from alerts.telegram import send
    from data.fetcher import get_fear_greed

    try:
        fg = await get_fear_greed()
    except Exception:
        fg = {"value": 50, "label": "Neutral"}

    cached_results = []
    for coin in cfg.COINS:
        cached = cache.get(f"signal_{coin}")
        if cached:
            cached_results.append(cached)

    cached_results.sort(key=lambda x: x.get("score", 0), reverse=True)

    btc_cached = cache.get("signal_BTC")
    btc_line   = ""
    if btc_cached:
        btc_market = btc_cached.get("market", {})
        btc_change = btc_market.get("change24", 0)
        btc_regime = btc_cached.get("regime", "--")
        sign       = "+" if btc_change >= 0 else ""
        btc_line   = f"BTC: `{sign}{btc_change:.2f}%` overnight — `{btc_regime}`\n"

    fg_val   = fg.get("value", 50)
    fg_label = fg.get("label", "Neutral")
    fg_emoji = (
        "🟢" if fg_val >= 60 else
        "🔴" if fg_val <= 30 else
        "🟡"
    )

    cats      = categorize_results(cached_results)
    tradeable = cats["tradeable"]
    watching  = cats["watching"]
    building  = cats["building"]

    setups_lines = []
    if tradeable:
        setups_lines.append("*Tradeable Now:*")
        for r in tradeable[:3]:
            g  = r.get("grade", "?")
            d  = r.get("direction", "?")
            s  = r.get("score", 0)
            em = "📈" if d == "LONG" else "📉"
            setups_lines.append(f"{em} `{r['coin']}` — Grade {g} ({s}/100)")

    if watching:
        setups_lines.append("\n*Watching:*")
        for r in watching[:3]:
            d      = r.get("direction", "?")
            s      = r.get("score", 0)
            em     = "📈" if d == "LONG" else "📉"
            expl   = r.get("explanation", {})
            reason = expl.get("no_trade_reason", "")
            short  = reason.split("\n")[2].strip() if reason and len(reason.split("\n")) > 2 else "setup building"
            setups_lines.append(f"{em} `{r['coin']}` — B ({s}/100) — {short}")

    if building and not tradeable and not watching:
        setups_lines.append("\n*Building:*")
        for r in building[:2]:
            setups_lines.append(f"👁 `{r['coin']}` — C ({r.get('score',0)}/100)")

    if not setups_lines:
        setups_lines.append("No setups in cache — trigger /scan for fresh data")

    risk_stats  = risk_guard.get_daily_stats()
    trades_left = risk_stats.get("remaining_trades", cfg.MAX_TRADES_PER_DAY)
    loss_left   = risk_stats.get("remaining_loss", cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT)

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
    outcome:         str,
    pnl:             float,
    close_reason:    str,
    health_at_close: str
):
    from alerts.telegram import send

    is_win  = outcome == "win"
    is_loss = outcome == "loss"

    result_emoji = "✅" if is_win else "❌" if is_loss else "⏹"
    pnl_str      = f"+${pnl:.4f}" if pnl >= 0 else f"-${abs(pnl):.4f}"

    cached      = cache.get(f"signal_{trade.coin}")
    explanation = cached.get("explanation", {}) if cached else {}
    thesis      = explanation.get("thesis", "")
    risk_thesis = explanation.get("risk_thesis", "")

    worked_lines = []
    watch_lines  = []

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
            if line and line.startswith("⚠") and line not in watch_lines:
                watch_lines.append(line)

    worked_block = "\n".join(worked_lines) if worked_lines else "No thesis data available"
    watch_block  = "\n".join(watch_lines[:3]) if watch_lines else "No risk flags at entry"

    grade_line = grade_accuracy_str(trade.grade)

    health_emoji = (
        "✅" if health_at_close == "HEALTHY"     else
        "⚠️" if health_at_close == "WARNING"     else
        "🚨" if health_at_close == "INVALIDATED" else
        "—"
    )

    thesis_held = (
        "Thesis held from entry to exit"   if health_at_close == "HEALTHY"     else
        "Thesis weakened during trade"     if health_at_close == "WARNING"     else
        "Thesis invalidated before close"  if health_at_close == "INVALIDATED" else
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