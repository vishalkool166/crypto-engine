import logging
from datetime import datetime, timezone, timedelta
from data.cache import cache
from config import cfg
from database import SessionLocal, Signal as SignalModel
from alerts.utils import now_ist_str, grade_accuracy_str, categorize_results

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist_full() -> str:
    return datetime.now(IST).strftime("%d %b %Y · %I:%M %p IST")


def _session_label() -> str:
    now  = datetime.now(timezone.utc)
    hour = now.hour + now.minute / 60
    if 13 <= hour < 16:
        return "London/NY Overlap"
    if 8 <= hour < 16:
        return "London Session"
    if 13 <= hour < 21:
        return "New York Session"
    if 0 <= hour < 8:
        return "Asian Session"
    return "Off Hours"


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

    await send(
        f"🌅 *Morning Briefing — London Open*\n"
        f"_{_now_ist_full()}_\n\n"
        f"{btc_line}"
        f"{fg_emoji} Fear & Greed: `{fg_val} — {fg_label}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{chr(10).join(setups_lines)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Session: `London Session` — High volume. Trend initiation common.\n"
        f"Next scan: next `:00/:15/:30/:45` UTC\n"
        f"Type /scan to scan now"
    )

    log.info("Morning briefing sent")


async def send_evening_briefing():
    from alerts.telegram import send
    from data.fetcher import get_fear_greed
    from alerts.scanner import get_db_stats

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

    stats = get_db_stats()

    setups_lines = []
    if tradeable:
        setups_lines.append("*Active Signals:*")
        for r in tradeable[:3]:
            g  = r.get("grade", "?")
            d  = r.get("direction", "?")
            s  = r.get("score", 0)
            em = "📈" if d == "LONG" else "📉"
            ml = r.get("ml_probability")
            ml_str = f" · ML:`{ml*100:.0f}%`" if ml is not None else ""
            setups_lines.append(f"{em} `{r['coin']}` — Grade {g} ({s}/100){ml_str}")
    elif watching:
        setups_lines.append("*Watching:*")
        for r in watching[:2]:
            d  = r.get("direction", "?")
            s  = r.get("score", 0)
            em = "📈" if d == "LONG" else "📉"
            setups_lines.append(f"{em} `{r['coin']}` — B ({s}/100)")
    else:
        setups_lines.append("No active setups — market quiet")

    today_pnl = 0.0
    today_trades = 0
    try:
        from datetime import date
        with SessionLocal() as db:
            today_str  = date.today().isoformat()
            today_sigs = db.query(SignalModel).filter(
                SignalModel.timestamp >= today_str,
                SignalModel.outcome.in_(["win", "loss"])
            ).all()
            today_pnl    = sum(float(s.pnl or 0) for s in today_sigs)
            today_trades = len(today_sigs)
    except Exception:
        pass

    pnl_str  = f"+${today_pnl:.4f}" if today_pnl >= 0 else f"-${abs(today_pnl):.4f}"
    pnl_emoji = "📈" if today_pnl >= 0 else "📉"

    await send(
        f"🌆 *Evening Briefing — NY Open*\n"
        f"_{_now_ist_full()}_\n\n"
        f"{fg_emoji} Fear & Greed: `{fg_val} — {fg_label}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{chr(10).join(setups_lines)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*Today Summary*\n"
        f"Closed trades: `{today_trades}`\n"
        f"{pnl_emoji} Today PnL: `{pnl_str}`\n"
        f"All-time WR: `{stats.get('win_rate', 0)}%`\n\n"
        f"Session: `New York Session` — High volume. Good for entries.\n"
        f"Next scan: next `:00/:15/:30/:45` UTC\n"
        f"Type /scan to scan now"
    )

    log.info("Evening briefing sent")