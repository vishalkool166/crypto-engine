import logging
from datetime import datetime, timezone, timedelta
from data.cache import cache
from config import cfg
from database import SessionLocal, Signal as SignalModel
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

    await send(
        f"🌅 *Morning Briefing — {now_ist_str()}*\n\n"
        f"{btc_line}"
        f"{fg_emoji} Fear & Greed: `{fg_val} — {fg_label}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{chr(10).join(setups_lines)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Next scan: next `:00/:15/:30/:45` UTC\n"
        f"Type /scan to scan now"
    )

    log.info("Morning briefing sent")