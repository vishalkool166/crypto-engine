import httpx
import logging
import time
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import Request
from config import cfg
from database import SessionLocal, get_session
from alerts.utils import categorize_results
from data.cache import cache

log = logging.getLogger(__name__)

BASE   = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}"
DOMAIN = cfg.DOMAIN

IST = timezone(timedelta(hours=5, minutes=30))

LONDON_OPEN  = 8
LONDON_CLOSE = 16
NY_OPEN      = 13
NY_CLOSE     = 21


def _now_ist() -> str:
    return datetime.now(IST).strftime("%I:%M %p IST")


def _now_ist_full() -> str:
    return datetime.now(IST).strftime("%d %b %Y · %I:%M %p IST")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _dashboard_button() -> dict:
    return {
        "inline_keyboard": [[{
            "text":    "Open Dashboard",
            "web_app": {"url": DOMAIN + "/app.html"}
        }]]
    }


def _get_cached(coin: str) -> dict | None:
    return cache.get_raw(f"signal_{coin}")


def _all_cached_signals() -> list:
    results = []
    for coin in cfg.COINS:
        cached = cache.get_raw(f"signal_{coin}")
        if cached:
            results.append(cached)
    return results


def _get_stats() -> dict:
    from alerts.scanner import get_db_stats
    return get_db_stats()


def _grade_block(label: str, data: dict) -> str:
    return (
        f"*Grade {label}*\n"
        f"Trades:   `{data.get('total', 0)}`\n"
        f"Wins:     `{data.get('wins', 0)}`\n"
        f"Losses:   `{data.get('losses', 0)}`\n"
        f"Win Rate: `{data.get('win_rate', 0)}%`\n"
        f"PnL:      `${data.get('total_pnl', 0)}`\n"
    )


def _session_status() -> dict:
    now_utc  = _now_utc()
    hour_utc = now_utc.hour + now_utc.minute / 60

    london_open  = LONDON_OPEN  <= hour_utc < LONDON_CLOSE
    ny_open      = NY_OPEN      <= hour_utc < NY_CLOSE
    overlap      = london_open and ny_open

    def mins_until(target_hour: float) -> int:
        now_mins    = now_utc.hour * 60 + now_utc.minute
        target_mins = int(target_hour * 60)
        diff        = target_mins - now_mins
        if diff < 0:
            diff += 1440
        return diff

    def fmt_mins(m: int) -> str:
        h = m // 60
        r = m % 60
        if h > 0:
            return f"{h}h {r}m"
        return f"{r}m"

    def utc_to_ist(h: int) -> str:
        ist_h = (h + 5) % 24
        ist_m = 30
        total = ist_h * 60 + ist_m
        hh    = total // 60 % 24
        mm    = total % 60
        suffix = "AM" if hh < 12 else "PM"
        hh12   = hh % 12 or 12
        return f"{hh12:02d}:{mm:02d} {suffix}"

    next_london_open  = fmt_mins(mins_until(LONDON_OPEN))
    next_london_close = fmt_mins(mins_until(LONDON_CLOSE))
    next_ny_open      = fmt_mins(mins_until(NY_OPEN))
    next_ny_close     = fmt_mins(mins_until(NY_CLOSE))

    if overlap:
        current    = "London / NY Overlap"
        quality    = "BEST — highest liquidity"
        quality_em = "A"
    elif london_open:
        current    = "London Session"
        quality    = "GOOD — European liquidity"
        quality_em = "B"
    elif ny_open:
        current    = "New York Session"
        quality    = "GOOD — US liquidity"
        quality_em = "B"
    else:
        current    = "Off Hours"
        quality    = "LOW — avoid new entries"
        quality_em = "C"

    return {
        "current":           current,
        "quality":           quality,
        "quality_em":        quality_em,
        "london_open":       london_open,
        "ny_open":           ny_open,
        "overlap":           overlap,
        "next_london_open":  next_london_open,
        "next_london_close": next_london_close,
        "next_ny_open":      next_ny_open,
        "next_ny_close":     next_ny_close,
        "london_ist_open":   utc_to_ist(LONDON_OPEN),
        "london_ist_close":  utc_to_ist(LONDON_CLOSE),
        "ny_ist_open":       utc_to_ist(NY_OPEN),
        "ny_ist_close":      utc_to_ist(NY_CLOSE),
        "overlap_ist_open":  utc_to_ist(NY_OPEN),
        "overlap_ist_close": utc_to_ist(LONDON_CLOSE),
    }


async def _post(endpoint: str, payload: dict):
    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured")
        return
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{BASE}/{endpoint}", json=payload, timeout=10)
            if r.status_code != 200:
                log.error(f"Telegram {endpoint} failed: {r.text}")
    except Exception as e:
        log.error(f"Telegram error: {e}")


async def send(message: str, reply_markup: dict = None):
    chunks = _split_message(message)
    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id":    cfg.TELEGRAM_CHAT_ID,
            "text":       chunk,
            "parse_mode": "Markdown"
        }
        if reply_markup and i == len(chunks) - 1:
            payload["reply_markup"] = reply_markup
        await _post("sendMessage", payload)


def _split_message(text: str, limit: int = 4000) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


async def register_webhook():
    webhook_url = f"{DOMAIN}/webhook/telegram"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{BASE}/setWebhook",
                json={
                    "url":          webhook_url,
                    "secret_token": cfg.WEBHOOK_SECRET
                },
                timeout=10
            )
            data = r.json()
            if data.get("ok"):
                log.info(f"Webhook registered: {webhook_url}")
            else:
                log.error(f"Webhook failed: {data}")
    except Exception as e:
        log.error(f"Webhook register error: {e}")


async def register_commands():
    commands = [
        {"command": "start",     "description": "Open Signal Engine dashboard"},
        {"command": "status",    "description": "Bot status overview"},
        {"command": "session",   "description": "Current session and next timings"},
        {"command": "scan",      "description": "Trigger manual scan"},
        {"command": "health",    "description": "All open trades health"},
        {"command": "ftstatus",  "description": "Freqtrade open trades"},
        {"command": "ftstart",   "description": "Start Freqtrade bot"},
        {"command": "ftstop",    "description": "Stop Freqtrade bot"},
        {"command": "sync",      "description": "Sync Freqtrade outcomes"},
        {"command": "btc",       "description": "BTC analysis"},
        {"command": "coin",      "description": "Any coin analysis — /coin ETH"},
        {"command": "pnl",       "description": "All time PnL"},
        {"command": "daily",     "description": "Today summary"},
        {"command": "ml",        "description": "ML model status"},
        {"command": "mode",      "description": "Current bot config"},
        {"command": "help",      "description": "Full command list"},
    ]
    try:
        async with httpx.AsyncClient() as client:
            r    = await client.post(
                f"{BASE}/setMyCommands",
                json={"commands": commands},
                timeout=10
            )
            data = r.json()
            if data.get("ok"):
                log.info("Telegram commands registered")
    except Exception as e:
        log.error(f"Commands register error: {e}")


async def handle_webhook(request: Request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if cfg.WEBHOOK_SECRET and secret != cfg.WEBHOOK_SECRET:
        log.warning("Webhook secret mismatch — rejected")
        return

    try:
        data    = await request.json()
        msg     = data.get("message", {})
        text    = msg.get("text", "").strip()
        chat_id = str(msg.get("chat", {}).get("id", ""))

        if chat_id != str(cfg.TELEGRAM_CHAT_ID):
            return

        await _handle_command(text, chat_id)

    except Exception as e:
        log.error(f"Webhook handler error: {e}")


async def _handle_command(text: str, chat_id: str = ""):
    t = text.lower().strip()

    if t.startswith("/coin"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        if not coin:
            await send("Usage: `/coin BTC`")
            return
        if coin in cfg.COINS:
            await _cmd_coin(coin)
        else:
            await send(
                f"`{coin}` not in your universe.\n\n"
                f"Your coins: `{', '.join(cfg.COINS[:10])}{'...' if len(cfg.COINS) > 10 else ''}`"
            )
        return

    handlers = {
        "/start":    _cmd_start,
        "/status":   _cmd_status,
        "/session":  _cmd_session,
        "/scan":     _cmd_scan,
        "/health":   _cmd_health,
        "/ftstatus": _cmd_ft_status,
        "/ftstart":  _cmd_ft_start,
        "/ftstop":   _cmd_ft_stop,
        "/sync":     _cmd_sync,
        "/btc":      _cmd_btc,
        "/pnl":      _cmd_pnl,
        "/daily":    _cmd_daily,
        "/ml":       _cmd_ml,
        "/mode":     _cmd_mode,
        "/help":     _cmd_help,
    }

    if t.startswith("/"):
        cmd     = t.split()[0]
        handler = handlers.get(cmd)
        if handler:
            await handler()
        else:
            await send("Unknown command. Type /help for the full list.")
        return

    try:
        from chatbot import chat
        response = await chat(text)
        await send(response)
    except Exception as e:
        log.error(f"Chatbot error: {e}")
        await send("Type /help for available commands.")


async def _cmd_start():
    mode = "LIVE" if not cfg.PAPER_TRADING else "PAPER"
    await send(
        f"*Signal Engine v5*\n"
        f"_{_now_ist_full()}_\n\n"
        f"Mode:   `{mode}`\n"
        f"Coins:  `{len(cfg.COINS)} scanning`\n"
        f"Grades: `{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n\n"
        f"Tap below to open your dashboard.",
        reply_markup=_dashboard_button()
    )


async def _cmd_status():
    stats     = _get_stats()
    from scheduler import get_next_scan_time
    next_scan = get_next_scan_time()
    sess      = _session_status()

    cached_results = _all_cached_signals()
    tradeable      = [
        r for r in cached_results
        if r.get("grade") in cfg.MIN_GRADE_TO_TRADE
        and r.get("direction") in ["LONG", "SHORT"]
    ]

    mode = "LIVE" if not cfg.PAPER_TRADING else "PAPER"

    await send(
        f"*Bot Status*\n"
        f"_{_now_ist_full()}_\n\n"
        f"State:    `RUNNING`\n"
        f"Mode:     `{mode}`\n"
        f"Session:  `{sess['current']}`\n"
        f"Coins:    `{len(cfg.COINS)} scanning`\n"
        f"Grades:   `{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n"
        f"Tradeable:`{len(tradeable)}`\n\n"
        f"Signals:  `{stats.get('total', 0)}` total\n"
        f"Closed:   `{stats.get('closed', 0)}`\n"
        f"Win Rate: `{stats.get('win_rate', 0)}%`\n\n"
        f"Next scan: `{next_scan}`",
        reply_markup=_dashboard_button()
    )


async def _cmd_session():
    s    = _session_status()
    now  = _now_utc()
    utc  = now.strftime("%H:%M UTC")

    london_status  = "OPEN" if s["london_open"] else "CLOSED"
    ny_status      = "OPEN" if s["ny_open"]     else "CLOSED"
    overlap_status = "ACTIVE" if s["overlap"]   else "INACTIVE"

    london_next  = f"closes in {s['next_london_close']}" if s["london_open"]  else f"opens in {s['next_london_open']}"
    ny_next      = f"closes in {s['next_ny_close']}"     if s["ny_open"]      else f"opens in {s['next_ny_open']}"
    overlap_next = f"ends in {s['next_london_close']}"   if s["overlap"]      else f"starts in {s['next_ny_open']}" if not s["ny_open"] else f"starts in {s['next_ny_open']}"

    quality_map = {
        "A": "Best — highest liquidity, take all A+/A signals",
        "B": "Good — normal liquidity, standard rules apply",
        "C": "Low — avoid new entries, manage existing trades",
    }

    await send(
        f"*Session Status*\n"
        f"_{utc} · {_now_ist()}_\n\n"
        f"*Current: {s['current']}*\n"
        f"Quality: `{s['quality']}`\n\n"
        f"*London*  `{london_status}`\n"
        f"Hours:  `{LONDON_OPEN:02d}:00 - {LONDON_CLOSE:02d}:00 UTC`\n"
        f"IST:    `{s['london_ist_open']} - {s['london_ist_close']}`\n"
        f"Status: _{london_next}_\n\n"
        f"*New York*  `{ny_status}`\n"
        f"Hours:  `{NY_OPEN:02d}:00 - {NY_CLOSE:02d}:00 UTC`\n"
        f"IST:    `{s['ny_ist_open']} - {s['ny_ist_close']}`\n"
        f"Status: _{ny_next}_\n\n"
        f"*Overlap*  `{overlap_status}`\n"
        f"Hours:  `{NY_OPEN:02d}:00 - {LONDON_CLOSE:02d}:00 UTC`\n"
        f"IST:    `{s['overlap_ist_open']} - {s['overlap_ist_close']}`\n"
        f"Status: _{overlap_next}_\n\n"
        f"_{quality_map.get(s['quality_em'], '')}_"
    )


async def _cmd_btc():
    await _cmd_coin("BTC")


async def _cmd_coin(coin: str):
    cached = _get_cached(coin)
    if not cached:
        await send(f"No data for `{coin}`. Run /scan first.")
        return

    market    = cached.get("market", {})
    grade     = cached.get("grade", "F")
    dir_      = cached.get("direction", "--")
    score     = cached.get("score", 0)
    sweep     = cached.get("sweep", {})
    disp      = cached.get("displacement", {})
    retest    = cached.get("retest", {})
    d1d       = cached.get("d1d", {})
    expl      = cached.get("explanation", {})
    ml_prob   = cached.get("ml_probability")
    actual_rr = cached.get("actual_rr", 0)
    tp_mult   = cached.get("tp_mult", 1.5)

    price   = market.get("price", 0)
    change  = market.get("change24", 0)
    funding = market.get("funding", 0) * 100
    sign    = "+" if change >= 0 else ""
    rsi     = d1d.get("rsi")
    adx     = d1d.get("adx")

    sig   = cached.get("signal", {})
    entry = sig.get("entry")
    sl    = sig.get("sl")
    tp1   = sig.get("tp1")

    ml_line = ""
    if ml_prob is not None:
        ml_line = f"ML Prob: `{ml_prob*100:.1f}%`\n"

    conf_label = expl.get("confidence_label", "")
    thesis     = expl.get("thesis", "")

    msg = (
        f"*{coin}USDT Analysis*\n"
        f"_{_now_ist()}_\n\n"
        f"Price:   `${price:,.4f}` ({sign}{change:.2f}%)\n"
        f"Grade:   `{grade}` · Score `{score}/100`\n"
        f"Signal:  `{dir_}`\n"
    )

    if conf_label:
        msg += f"Conf:    `{conf_label}`\n"

    if ml_line:
        msg += ml_line

    msg += (
        f"\nRegime:  `{cached.get('regime', '--')}`\n"
        f"Session: `{cached.get('session', '--')}`\n"
    )

    if rsi and adx:
        msg += (
            f"\nRSI:     `{rsi:.1f}`\n"
            f"ADX:     `{adx:.1f}`\n"
            f"Funding: `{funding:.4f}%`\n"
        )

    if entry and sl and tp1:
        msg += (
            f"\nEntry:   `{entry:.4f}`\n"
            f"SL:      `{sl:.4f}`\n"
            f"TP:      `{tp1:.4f}` ({tp_mult}x)\n"
            f"R:R:     `1:{actual_rr}`\n"
        )

    msg += (
        f"\nSweep:   `{'Yes' if sweep.get('confirmed') else 'No'} ({sweep.get('score',0)}/12)`\n"
        f"Disp:    `{'Yes' if disp.get('confirmed') else 'No'} ({disp.get('score',0)}/11)`\n"
        f"Retest:  `{'Yes' if retest.get('confirmed') else 'No'} ({retest.get('score',0)}/12)`\n"
    )

    if thesis:
        msg += f"\n_{thesis}_"

    await send(msg, reply_markup=_dashboard_button())


async def _cmd_pnl():
    stats = _get_stats()
    await send(
        f"*PnL Report*\n"
        f"_{_now_ist()}_\n\n"
        f"Total signals: `{stats.get('total', 0)}`\n"
        f"Closed:        `{stats.get('closed', 0)}`\n"
        f"Wins:          `{stats.get('wins', 0)}`\n"
        f"Losses:        `{stats.get('losses', 0)}`\n"
        f"Win Rate:      `{stats.get('win_rate', 0)}%`\n"
        f"Total PnL:     `${stats.get('total_pnl', 0)}`",
        reply_markup=_dashboard_button()
    )


async def _cmd_daily():
    from datetime import date
    stats = _get_stats()

    today_pnl    = 0.0
    today_trades = 0
    try:
        with SessionLocal() as db:
            from database import Signal as SignalModel
            today_str  = date.today().isoformat()
            today_sigs = db.query(SignalModel).filter(
                SignalModel.timestamp >= today_str,
                SignalModel.outcome.in_(["win", "loss"])
            ).all()
            today_pnl    = sum(float(s.pnl or 0) for s in today_sigs)
            today_trades = len(today_sigs)
    except Exception:
        pass

    sign    = "+" if today_pnl >= 0 else "-"
    pnl_str = f"{sign}${abs(today_pnl):.4f}"

    await send(
        f"*Daily Summary*\n"
        f"_{_now_ist_full()}_\n\n"
        f"Today trades: `{today_trades}`\n"
        f"Today PnL:    `{pnl_str}`\n\n"
        f"All-time closed: `{stats.get('closed', 0)}`\n"
        f"Win Rate:        `{stats.get('win_rate', 0)}%`\n"
        f"Total PnL:       `${stats.get('total_pnl', 0)}`",
        reply_markup=_dashboard_button()
    )


async def _cmd_ml():
    from ml.eligibility import get_ml_status
    status = get_ml_status()

    closed   = status.get("closed_trades", 0)
    required = status.get("required", 100)
    enabled  = status.get("ml_enabled", False)
    message  = status.get("message", "")

    pct        = min(100, int(closed / required * 100))
    bar_filled = pct // 10
    bar        = "█" * bar_filled + "░" * (10 - bar_filled)

    top_features = status.get("top_features", [])
    top_str = ""
    if top_features:
        top_str = "\n*Top Features:*\n" + "\n".join(
            f"  `{f['feature']}` — `{f['importance']}`"
            for f in top_features[:3]
        )

    await send(
        f"*ML Status*\n\n"
        f"Status: `{'ACTIVE' if enabled else 'Collecting data'}`\n\n"
        f"Progress: `{closed}/{required}` trades\n"
        f"`{bar}` {pct}%\n\n"
        f"{message}"
        f"{top_str}"
    )


async def _cmd_mode():
    mode   = "LIVE" if not cfg.PAPER_TRADING else "PAPER"
    grades = ', '.join(cfg.MIN_GRADE_TO_TRADE)
    await send(
        f"*Bot Configuration*\n\n"
        f"Mode:      `{mode}`\n"
        f"Coins:     `{len(cfg.COINS)} coins`\n"
        f"Grades:    `{grades}`\n"
        f"Scan:      `every :00/:15/:30/:45 UTC`\n"
        f"Execution: `Freqtrade`\n"
        f"ML:        `{'Active' if cfg.ML_ENABLED else 'Collecting data'}`\n"
    )


async def _cmd_sync():
    await send("Syncing Freqtrade outcomes...")
    try:
        from trade.sync import sync_freqtrade_outcomes
        result    = await sync_freqtrade_outcomes()
        synced    = result.get("synced", 0)
        unmatched = result.get("unmatched", 0)
        total     = result.get("total", 0)
        error     = result.get("error", "")

        if error:
            await send(f"Sync failed: `{error}`")
            return

        await send(
            f"*Sync Complete*\n\n"
            f"Freqtrade closed: `{total}`\n"
            f"Synced:           `{synced}`\n"
            f"Unmatched:        `{unmatched}`"
        )
    except Exception as e:
        await send(f"Sync error: `{str(e)}`")


async def _ft_api_get(path: str) -> dict | None:
    try:
        from api.freqtrade import _get_ft_token
        token = await _get_ft_token()
        if not token:
            return None
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{cfg.FREQTRADE_URL}/api/v1{path}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            return r.json()
    except Exception as e:
        log.error(f"FT API error {path}: {e}")
        return None


async def _ft_api_post(path: str, body: dict = None) -> dict | None:
    try:
        from api.freqtrade import _get_ft_token
        token = await _get_ft_token()
        if not token:
            return None
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{cfg.FREQTRADE_URL}/api/v1{path}",
                headers={"Authorization": f"Bearer {token}"},
                json=body or {},
                timeout=10
            )
            return r.json()
    except Exception as e:
        log.error(f"FT API post error {path}: {e}")
        return None


async def _cmd_ft_status():
    data = await _ft_api_get("/status")
    if data is None:
        await send("Freqtrade unavailable")
        return

    if not data or not isinstance(data, list):
        await send(
            f"*Freqtrade Status*\n"
            f"_{_now_ist()}_\n\n"
            f"No open trades.",
            reply_markup=_dashboard_button()
        )
        return

    lines = [f"*Freqtrade — {len(data)} Open Trade(s)*\n_{_now_ist()}_\n"]

    for t in data:
        pair    = t.get("pair", "--")
        coin    = pair.replace("/USDT:USDT", "").replace("/USDT", "")
        pnl     = float(t.get("profit_abs", 0))
        pnl_pct = float(t.get("profit_ratio", 0)) * 100
        sign    = "+" if pnl >= 0 else "-"
        pnl_str = f"{sign}${abs(pnl):.4f}"
        side    = "LONG" if not t.get("is_short") else "SHORT"
        lev     = t.get("leverage", "--")
        stake   = t.get("stake_amount", 0)

        open_date = t.get("open_date", "")
        duration  = "--"
        try:
            if open_date:
                s        = open_date.strip().replace(' ', 'T')
                s        = s + '+00:00' if '+' not in s and 'Z' not in s else s
                s        = s.replace('Z', '+00:00')
                open_dt  = datetime.fromisoformat(s)
                diff     = datetime.now(timezone.utc) - open_dt
                mins     = int(diff.total_seconds() / 60)
                hrs      = mins // 60
                rem_mins = mins % 60
                duration = f"{hrs}h {rem_mins}m" if hrs > 0 else f"{mins}m"
        except Exception:
            pass

        try:
            from trade.health_monitor import get_health_from_redis
            health       = get_health_from_redis(coin)
            health_state = health.get("state", "UNKNOWN") if health else "Checking"
        except Exception:
            health_state = "Checking"

        lines.append(
            f"`{pair}` {side}\n"
            f"PnL: `{pnl_str}` ({pnl_pct:.2f}%) · Open: `{duration}`\n"
            f"Stake: `${float(stake):.2f}` · Lev: `{lev}x`\n"
            f"Health: `{health_state}`\n"
        )

    await send("\n".join(lines), reply_markup=_dashboard_button())


async def _cmd_ft_start():
    data = await _ft_api_post("/start")
    if data is None:
        await send("Freqtrade unavailable")
        return
    await send(f"*Freqtrade Started*\n\nStatus: `{data.get('status', 'unknown')}`")


async def _cmd_ft_stop():
    data = await _ft_api_post("/stop")
    if data is None:
        await send("Freqtrade unavailable")
        return
    await send(f"*Freqtrade Stopped*\n\nStatus: `{data.get('status', 'unknown')}`")


async def _cmd_health():
    data = await _ft_api_get("/status")
    if data is None:
        await send("Freqtrade unavailable")
        return

    if not data or not isinstance(data, list):
        await send(
            f"*Trade Health*\n_{_now_ist()}_\n\nNo open trades.",
            reply_markup=_dashboard_button()
        )
        return

    lines = [f"*Trade Health — {len(data)} Open*\n_{_now_ist()}_\n"]

    for t in data:
        pair  = t.get("pair", "--")
        coin  = pair.replace("/USDT:USDT", "").replace("/USDT", "")
        pnl   = float(t.get("profit_abs", 0))
        sign  = "+" if pnl >= 0 else "-"
        pnl_str = f"{sign}${abs(pnl):.4f}"
        side  = "LONG" if not t.get("is_short") else "SHORT"

        try:
            from trade.health_monitor import get_health_from_redis
            health       = get_health_from_redis(coin)
            health_state = health.get("state", "UNKNOWN") if health else "Checking"
            failures     = health.get("failures", []) if health else []
            warnings     = health.get("warnings", []) if health else []
        except Exception:
            health_state = "Checking"
            failures     = []
            warnings     = []

        lines.append(f"`{coin}` {side} — `{health_state}` · `{pnl_str}`")

        if failures:
            lines.append(f"  _{failures[0]}_")
        elif warnings:
            lines.append(f"  _{warnings[0]}_")

        lines.append("")

    await send("\n".join(lines), reply_markup=_dashboard_button())


async def _cmd_scan():
    await send("Manual scan started — takes 1-2 minutes.")
    try:
        from alerts.scanner import scan_all_coins
        await scan_all_coins()
    except Exception as e:
        await send(f"Scan failed: `{str(e)}`")


async def _cmd_help():
    sess = _session_status()
    await send(
        f"*Signal Engine v5 — Commands*\n"
        f"_Session: {sess['current']}_\n\n"
        f"*MONITORING*\n"
        f"/status   — bot status overview\n"
        f"/session  — current session + next timings\n"
        f"/health   — open trades health\n"
        f"/ftstatus — Freqtrade open trades\n\n"
        f"*ACTIONS*\n"
        f"/scan     — trigger manual scan\n"
        f"/ftstart  — start Freqtrade bot\n"
        f"/ftstop   — stop Freqtrade bot\n"
        f"/sync     — sync outcomes\n\n"
        f"*ANALYSIS*\n"
        f"/btc      — BTC analysis\n"
        f"/coin ETH — any coin analysis\n\n"
        f"*PERFORMANCE*\n"
        f"/pnl      — all time PnL\n"
        f"/daily    — today summary\n\n"
        f"*SYSTEM*\n"
        f"/ml       — ML model status\n"
        f"/mode     — bot configuration\n\n"
        f"_Tap below to open full dashboard._",
        reply_markup=_dashboard_button()
    )


async def send_signal(signal: dict, coin: str, regime: str, session: str):
    if signal.get("grade") not in cfg.MIN_GRADE_TO_TRADE:
        return
    if signal.get("direction") not in ["LONG", "SHORT"]:
        return
    if not signal.get("entry"):
        return

    grade     = signal.get("grade", "?")
    direction = signal.get("direction", "?")
    score     = signal.get("score", 0)
    entry     = signal.get("entry", 0)
    sl        = signal.get("sl", 0)
    tp1       = signal.get("tp1", 0)
    sl_pct    = signal.get("sl_pct", 0)
    risk_amt  = signal.get("risk_amt", 0)
    tp_mult   = signal.get("tp_mult", 1.5)
    actual_rr = signal.get("actual_rr", 0)
    ml_prob   = signal.get("ml_probability")

    explanation = signal.get("explanation", {})
    thesis      = explanation.get("thesis", "")
    conf_label  = explanation.get("confidence_label", "")

    ml_line    = f"ML:      `{ml_prob*100:.1f}%`\n" if ml_prob is not None else ""
    conf_line  = f"Conf:    `{conf_label} ({score}/100)`\n" if conf_label else f"Score:   `{score}/100`\n"
    grade_note = "_Grade B — paper mode only_\n\n" if grade == "B" else ""

    await send(
        f"*Grade {grade} — {direction}*\n\n"
        f"*{coin}USDT*\n"
        f"{conf_line}"
        f"{ml_line}"
        f"Regime:  `{regime}`\n"
        f"Session: `{session}`\n"
        f"Time:    `{_now_ist()}`\n\n"
        f"Entry:   `{entry:.4f}`\n"
        f"SL:      `{sl:.4f}` ({sl_pct:.2f}%)\n"
        f"TP:      `{tp1:.4f}` ({tp_mult}x)\n"
        f"R:R:     `1:{actual_rr}`\n"
        f"Risk:    `${risk_amt:.2f}`\n\n"
        f"{grade_note}"
        f"{('_' + thesis + '_') if thesis else ''}",
        reply_markup=_dashboard_button()
    )


async def send_scan_summary(results: list):
    from alerts.utils import categorize_results
    from scheduler import get_next_scan_time

    cats      = categorize_results(results)
    tradeable = cats["tradeable"]
    watching  = cats["watching"]
    next_scan = get_next_scan_time()
    sess      = _session_status()

    if tradeable:
        lines = [
            f"*Scan Complete — {_now_ist()}*\n"
            f"Session: `{sess['current']}`\n"
            f"{len(tradeable)} tradeable signal(s)\n\n"
        ]
        for r in tradeable[:3]:
            g         = r.get("grade", "?")
            direction = r.get("direction", "?")
            score     = r.get("score", 0)
            coin      = r.get("coin", "?")
            actual_rr = r.get("actual_rr", 0)
            ml_prob   = r.get("ml_probability")
            ml_str    = f" · ML:`{ml_prob*100:.0f}%`" if ml_prob is not None else ""
            lines.append(
                f"*{coin}* — Grade {g} ({score}/100){ml_str}\n"
                f"{direction} · R:R `1:{actual_rr}`\n"
            )
        lines.append(f"\nNext scan: `{next_scan}`")
        await send("\n".join(lines), reply_markup=_dashboard_button())
        return

    lines = [
        f"*No Tradeable Signals — {_now_ist()}*\n"
        f"Session: `{sess['current']}`\n\n"
    ]

    if watching:
        lines.append("*Closest Setups:*")
        for r in watching[:2]:
            d      = r.get("direction", "?")
            s      = r.get("score", 0)
            hards  = (r.get("no_trade", {}) or {}).get("hard_blocks", [])
            reason = hards[0]["reason"] if hards else "setup building"
            lines.append(f"`{r['coin']}` — B ({s}/100)\n_{reason}_\n")

    lines.append(f"\nNext scan: `{next_scan}`")
    await send("\n".join(lines), reply_markup=_dashboard_button())