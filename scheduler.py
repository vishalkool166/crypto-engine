import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron      import CronTrigger
from apscheduler.triggers.interval  import IntervalTrigger

log       = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="UTC")
IST       = timezone(timedelta(hours=5, minutes=30))


async def job_scan():
    try:
        from alerts.scanner import scan_all_coins
        await scan_all_coins()
    except Exception as e:
        log.error("job_scan: %s", e)


async def job_monitor():
    try:
        from trade.monitor import run_monitor_cycle
        await run_monitor_cycle()
    except Exception as e:
        log.error("job_monitor: %s", e)


async def job_cooldown_tick():
    try:
        from engines.state import tick_cooldowns
        tick_cooldowns()
    except Exception as e:
        log.error("job_cooldown_tick: %s", e)


async def job_session_cleanup():
    try:
        from saas.sessions import cleanup_expired_sessions
        count = cleanup_expired_sessions()
        if count:
            log.info("Session cleanup: %s removed", count)
    except Exception as e:
        log.error("job_session_cleanup: %s", e)


async def job_btc_cache():
    try:
        from data.fetcher import fetch_and_store
        from engines.indicators import calculate_all
        from data.cache import cache
        df_4h = await fetch_and_store("BTC", "4h", limit=200)
        df_1h = await fetch_and_store("BTC", "1h", limit=300)
        cache.set("btc_4h_data", calculate_all(df_4h, timeframe="4h"), ttl=900)
        cache.set("btc_1h_data", calculate_all(df_1h, timeframe="1h"), ttl=900)
    except Exception as e:
        log.error("job_btc_cache: %s", e)


async def job_rag_reindex():
    try:
        from rag.indexer import run_incremental_index
        results = run_incremental_index()
        total   = sum(results.values())
        if total > 0:
            log.info("RAG incremental index: %s new chunks", total)
    except Exception as e:
        log.error("job_rag_reindex: %s", e)


async def job_performance_summary():
    try:
        from ml.performance_tracker import get_overall_stats, get_recent_trend
        from alerts.telegram import send

        stats = get_overall_stats(min_trades=1)
        trend = get_recent_trend(window=20)

        if not stats or stats.get("error"):
            return

        total = stats.get("total", 0)
        if total == 0:
            return

        wr      = stats.get("win_rate",      0)
        pnl     = stats.get("total_pnl",     0)
        pf      = stats.get("profit_factor", 0)
        dd      = stats.get("max_drawdown",  0)
        t_trend = trend.get("trend",         "unknown")
        r_wr    = trend.get("recent_win_rate", 0)

        trend_emoji = (
            "📈" if t_trend == "improving"
            else "📉" if t_trend == "degrading"
            else "➡️"
        )

        await send(
            f"📊 *Daily Performance Summary*\n\n"
            f"Total trades:   `{total}`\n"
            f"Win rate:       `{wr:.1f}%`\n"
            f"Total PnL:      `${pnl:.2f}`\n"
            f"Profit factor:  `{pf}`\n"
            f"Max drawdown:   `{dd:.1f}%`\n\n"
            f"{trend_emoji} Recent trend: `{t_trend}`\n"
            f"Recent WR (20): `{r_wr:.1f}%`\n\n"
            f"System version: `{__import__('config').cfg.SYSTEM_VERSION}`"
        )

    except Exception as e:
        log.error("job_performance_summary: %s", e)


async def job_morning_briefing():
    try:
        from alerts.briefing import send_morning_briefing
        await send_morning_briefing()
    except Exception as e:
        log.error("job_morning_briefing: %s", e)


async def job_evening_briefing():
    try:
        from alerts.briefing import send_evening_briefing
        await send_evening_briefing()
    except Exception as e:
        log.error("job_evening_briefing: %s", e)


async def job_binance_account_snapshot():
    try:
        from trade.binance_sync import periodic_account_snapshot
        await periodic_account_snapshot()
    except Exception as e:
        log.error("job_binance_account_snapshot: %s", e)


async def job_binance_sync_unsynced():
    try:
        from trade.binance_sync import sync_unsynced_trades
        count = await sync_unsynced_trades()
        if count:
            log.info("Binance sync: %s unsynced trades processed", count)
    except Exception as e:
        log.error("job_binance_sync_unsynced: %s", e)


async def job_monthly_report():
    try:
        from reports.monthly_report import send_monthly_report_telegram
        await send_monthly_report_telegram()
    except Exception as e:
        log.error("job_monthly_report: %s", e)


async def job_funding_rates():
    try:
        from data.fetcher import get_funding_rate
        from redis_client import get_redis
        from config import cfg
        r = get_redis()
        if not r:
            return
        for coin in cfg.COINS:
            try:
                rate = await get_funding_rate(coin)
                r.setex(f"funding:{coin}USDT", 3600, str(rate))
            except Exception as e:
                log.warning("funding rate %s: %s", coin, e)
    except Exception as e:
        log.error("job_funding_rates: %s", e)


async def job_rs_refresh():
    try:
        from engines.relative_strength import invalidate_cache
        invalidate_cache()
    except Exception as e:
        log.error("job_rs_refresh: %s", e)


async def job_indian_refresh_session():
    from alerts.telegram import send

    max_attempts = 3
    wait_seconds = 60

    for attempt in range(1, max_attempts + 1):
        try:
            from engines.indian.auth import refresh_session, is_session_valid
            log.info("AngelOne session refresh attempt %s/%s", attempt, max_attempts)

            api = refresh_session()

            if api and is_session_valid():
                from engines.indian.instruments import refresh_instruments
                refresh_instruments()
                log.info("AngelOne session refreshed successfully on attempt %s", attempt)
                return

            log.warning(
                "AngelOne session refresh failed attempt %s/%s",
                attempt, max_attempts
            )

            if attempt < max_attempts:
                import asyncio
                log.info("Waiting %ss before retry...", wait_seconds)
                await asyncio.sleep(wait_seconds)

        except Exception as e:
            log.error("job_indian_refresh_session attempt %s: %s", attempt, e)
            if attempt < max_attempts:
                import asyncio
                await asyncio.sleep(wait_seconds)

    log.error("AngelOne session refresh failed after %s attempts", max_attempts)
    try:
        await send(
            f"🚨 *AngelOne Session Failed*\n\n"
            f"All {max_attempts} login attempts failed.\n"
            f"Indian market signals disabled.\n\n"
            f"Check credentials in .env\n"
            f"Run `/india` to verify status"
        )
    except Exception as e:
        log.error("Failed to send Telegram alert: %s", e)


async def job_indian_session_backup():
    try:
        from engines.indian.auth import is_session_valid, refresh_session
        from engines.indian.instruments import refresh_instruments

        if is_session_valid():
            log.debug("AngelOne backup check — session still valid")
            return

        log.warning("AngelOne backup check — session invalid, attempting recovery")

        api = refresh_session()
        if api and is_session_valid():
            refresh_instruments()
            log.info("AngelOne session recovered by backup job")
            try:
                from alerts.telegram import send
                await send(
                    "✅ *AngelOne Session Recovered*\n\n"
                    "Backup session check restored the connection.\n"
                    "Indian market signals active."
                )
            except Exception:
                pass
        else:
            log.error("AngelOne backup session recovery also failed")

    except Exception as e:
        log.error("job_indian_session_backup: %s", e)


async def job_indian_data_refresh():
    try:
        from engines.indian.data import is_market_open, refresh_indian_data, _is_rate_limited
        from engines.indian.instruments import get_instruments
        from config import cfg

        if not is_market_open():
            return

        if _is_rate_limited():
            log.warning("job_indian_data_refresh: rate limited — skipping")
            return

        instruments = get_instruments()
        for name in cfg.INDIAN_INSTRUMENTS:
            inst = instruments.get(name)
            if not inst:
                continue
            result = refresh_indian_data(inst["token"], name)
            if result.get("rate_limited"):
                log.warning("job_indian_data_refresh: rate limited after %s", name)
                break
            if result.get("success"):
                log.debug(
                    "Indian data refreshed: %s ltp=%.2f range=%.2f",
                    name,
                    result.get("ltp", 0),
                    result.get("day_range", 0),
                )

    except Exception as e:
        log.error("job_indian_data_refresh: %s", e)


async def job_indian_orb_setup():
    try:
        from engines.indian.data import is_orb_ready
        if not is_orb_ready():
            return
        from engines.indian.scanner import setup_orb, _get_day_range_so_far
        from engines.indian.instruments import get_instrument
        from engines.indian.strategy import MIN_ORB_SIZE, MAX_ORB_SIZE, MIN_DAY_RANGE
        from alerts.telegram import send
        from config import cfg

        result = setup_orb()

        for name in cfg.INDIAN_INSTRUMENTS:
            inst = get_instrument(name)
            if not inst:
                continue

            day_range = _get_day_range_so_far(inst["token"])

            if not result or name not in result:
                await send(
                    f"🇮🇳 *{name} Day Setup*\n\n"
                    f"❌ ORB not available\n\n"
                    f"Status: `Skipping today`"
                )
                continue

            orb      = result[name]
            orb_size = orb["size"]

            orb_ok  = MIN_ORB_SIZE <= orb_size <= MAX_ORB_SIZE
            day_ok  = day_range >= MIN_DAY_RANGE

            orb_emoji = "✅" if orb_ok  else "❌"
            day_emoji = "✅" if day_ok  else "❌"

            if orb_ok and day_ok:
                status = "Watching for breakout from 10am"
            else:
                reasons = []
                if not orb_ok:
                    if orb_size < MIN_ORB_SIZE:
                        reasons.append(f"ORB too tight ({orb_size:.0f} pts)")
                    else:
                        reasons.append(f"ORB too wide ({orb_size:.0f} pts)")
                if not day_ok:
                    reasons.append(f"Day range too small ({day_range:.0f} pts)")
                status = "Skipping today — " + " + ".join(reasons)

            await send(
                f"🇮🇳 *{name} Day Setup*\n\n"
                f"ORB High:  `{orb['high']:.2f}`\n"
                f"ORB Low:   `{orb['low']:.2f}`\n"
                f"ORB Range: `{orb_size:.0f} pts` {orb_emoji}\n"
                f"Day Range: `{day_range:.0f} pts` {day_emoji}\n\n"
                f"Status: `{status}`"
            )

            log.info(
                "Indian ORB setup: %s high=%.2f low=%.2f size=%.2f",
                name, orb["high"], orb["low"], orb_size
            )

    except Exception as e:
        log.error("job_indian_orb_setup: %s", e)


async def job_indian_scan():
    try:
        from engines.indian.data import is_orb_ready
        if not is_orb_ready():
            return
        from engines.indian.scanner import scan_all
        signals = await scan_all()
        if signals:
            log.info("Indian scan: %s signals fired", len(signals))
    except Exception as e:
        log.error("job_indian_scan: %s", e)


async def job_indian_track():
    try:
        from engines.indian.data import is_market_open
        if not is_market_open():
            return
        from engines.indian.tracker import track_outcomes
        await track_outcomes()
    except Exception as e:
        log.error("job_indian_track: %s", e)


async def job_indian_close():
    try:
        from engines.indian.tracker import track_outcomes
        from engines.indian.scanner import get_today_signals, get_orb_levels
        from engines.indian.strategy import MIN_DAY_RANGE
        from engines.indian.instruments import get_instrument
        from engines.indian.scanner import _get_day_range_so_far
        from alerts.telegram import send
        from config import cfg
        from database import SessionLocal, Signal as SignalModel

        await track_outcomes()
        log.info("Indian market close: forced outcome check")

        for name in cfg.INDIAN_INSTRUMENTS:
            today_signals = get_today_signals()

            if not today_signals:
                inst      = get_instrument(name)
                day_range = _get_day_range_so_far(inst["token"]) if inst else 0

                if day_range < MIN_DAY_RANGE:
                    reason = f"Day range too small ({day_range:.0f} pts)"
                else:
                    orb = get_orb_levels(name)
                    if not orb:
                        reason = "ORB not available"
                    else:
                        reason = "No breakout today"

                await send(
                    f"🇮🇳 *{name} End of Day*\n\n"
                    f"No signal today\n"
                    f"Reason: `{reason}`"
                )
                continue

            with SessionLocal() as db:
                from datetime import date, timezone, datetime as dt
                today_start = dt(
                    date.today().year,
                    date.today().month,
                    date.today().day,
                    tzinfo=timezone.utc,
                )
                closed = db.query(SignalModel).filter(
                    SignalModel.market    == "indian",
                    SignalModel.timestamp >= today_start,
                    SignalModel.outcome.in_(["win", "loss", "timeout"]),
                ).all()

                pending = db.query(SignalModel).filter(
                    SignalModel.market    == "indian",
                    SignalModel.timestamp >= today_start,
                    SignalModel.outcome   == "pending",
                ).all()

                month_start = dt(
                    date.today().year,
                    date.today().month,
                    1,
                    tzinfo=timezone.utc,
                )
                month_sigs = db.query(SignalModel).filter(
                    SignalModel.market    == "indian",
                    SignalModel.timestamp >= month_start,
                    SignalModel.outcome.in_(["win", "loss"]),
                ).all()

            month_pts = sum(float(s.pnl or 0) for s in month_sigs)

            if not closed and pending:
                await send(
                    f"🇮🇳 *{name} End of Day*\n\n"
                    f"Signal fired but still pending\n"
                    f"Check manually on AngelOne\n\n"
                    f"This month: `{month_pts:+.0f} pts`"
                )
                continue

            lines = [f"🇮🇳 *{name} End of Day*\n"]

            for s in closed:
                pnl    = float(s.pnl or 0)
                emoji  = "✅" if s.outcome == "win" else "❌" if s.outcome == "loss" else "⏱️"
                rupees = round(pnl * 15, 0)
                sign   = "+" if rupees >= 0 else ""
                lines.append(
                    f"{emoji} {s.direction} `{s.outcome.upper()}` "
                    f"`{pnl:+.0f} pts` = `₹{sign}{rupees:.0f}`"
                )

            today_pts = sum(float(s.pnl or 0) for s in closed)
            lines.append(f"\nToday: `{today_pts:+.0f} pts`")
            lines.append(f"This month: `{month_pts:+.0f} pts`")

            await send("\n".join(lines))

    except Exception as e:
        log.error("job_indian_close: %s", e)


def get_next_scan_time() -> str:
    now     = datetime.now(timezone.utc)
    minute  = now.minute
    buckets = [0, 15, 30, 45]
    for b in buckets:
        if minute < b:
            next_utc = now.replace(minute=b, second=0, microsecond=0)
            return next_utc.astimezone(IST).strftime("%I:%M %p IST")
    next_utc = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return next_utc.astimezone(IST).strftime("%I:%M %p IST")


def get_next_scan_epoch() -> int:
    now     = datetime.now(timezone.utc)
    minute  = now.minute
    buckets = [0, 15, 30, 45]
    for b in buckets:
        if minute < b:
            return int(
                now.replace(minute=b, second=0, microsecond=0).timestamp() * 1000
            )
    next_hour = now.replace(
        hour        = (now.hour + 1) % 24,
        minute      = 0,
        second      = 0,
        microsecond = 0,
    )
    return int(next_hour.timestamp() * 1000)


def start_scheduler():
    scheduler.add_job(
        job_scan,
        trigger          = CronTrigger(minute="0,15,30,45", timezone="UTC"),
        id               = "scan",
        replace_existing = True,
    )
    scheduler.add_job(
        job_btc_cache,
        trigger          = IntervalTrigger(minutes=30),
        id               = "btc_cache",
        replace_existing = True,
    )
    scheduler.add_job(
        job_monitor,
        trigger          = IntervalTrigger(seconds=30),
        id               = "monitor",
        replace_existing = True,
    )
    scheduler.add_job(
        job_cooldown_tick,
        trigger          = IntervalTrigger(minutes=30),
        id               = "cooldown_tick",
        replace_existing = True,
    )
    scheduler.add_job(
        job_session_cleanup,
        trigger          = IntervalTrigger(hours=1),
        id               = "session_cleanup",
        replace_existing = True,
    )
    scheduler.add_job(
        job_rag_reindex,
        trigger          = IntervalTrigger(minutes=30),
        id               = "rag_reindex",
        replace_existing = True,
    )
    scheduler.add_job(
        job_performance_summary,
        trigger          = CronTrigger(hour=8, minute=0, timezone="UTC"),
        id               = "performance_summary",
        replace_existing = True,
    )
    scheduler.add_job(
        job_morning_briefing,
        trigger          = CronTrigger(hour=2, minute=30, timezone="UTC"),
        id               = "morning_briefing",
        replace_existing = True,
    )
    scheduler.add_job(
        job_evening_briefing,
        trigger          = CronTrigger(hour=14, minute=30, timezone="UTC"),
        id               = "evening_briefing",
        replace_existing = True,
    )
    scheduler.add_job(
        job_binance_account_snapshot,
        trigger          = IntervalTrigger(minutes=15),
        id               = "binance_account_snapshot",
        replace_existing = True,
    )
    scheduler.add_job(
        job_binance_sync_unsynced,
        trigger          = IntervalTrigger(hours=1),
        id               = "binance_sync_unsynced",
        replace_existing = True,
    )
    scheduler.add_job(
        job_monthly_report,
        trigger          = CronTrigger(day=1, hour=9, minute=0, timezone="UTC"),
        id               = "monthly_report",
        replace_existing = True,
    )
    scheduler.add_job(
        job_funding_rates,
        trigger          = IntervalTrigger(hours=1),
        id               = "funding_rates",
        replace_existing = True,
    )
    scheduler.add_job(
        job_rs_refresh,
        trigger          = IntervalTrigger(minutes=15),
        id               = "rs_refresh",
        replace_existing = True,
    )
    scheduler.add_job(
        job_indian_refresh_session,
        trigger          = CronTrigger(hour=3, minute=30, timezone="UTC"),
        id               = "indian_refresh_session",
        replace_existing = True,
    )
    scheduler.add_job(
        job_indian_session_backup,
        trigger          = CronTrigger(hour=4, minute=0, timezone="UTC"),
        id               = "indian_session_backup",
        replace_existing = True,
    )
    scheduler.add_job(
        job_indian_data_refresh,
        trigger          = IntervalTrigger(minutes=5),
        id               = "indian_data_refresh",
        replace_existing = True,
    )
    scheduler.add_job(
        job_indian_orb_setup,
        trigger          = CronTrigger(hour=4, minute=5, timezone="UTC"),
        id               = "indian_orb_setup",
        replace_existing = True,
    )
    scheduler.add_job(
        job_indian_scan,
        trigger          = IntervalTrigger(minutes=5),
        id               = "indian_scan",
        replace_existing = True,
    )
    scheduler.add_job(
        job_indian_track,
        trigger          = IntervalTrigger(minutes=5),
        id               = "indian_track",
        replace_existing = True,
    )
    scheduler.add_job(
        job_indian_close,
        trigger          = CronTrigger(hour=9, minute=45, timezone="UTC"),
        id               = "indian_close",
        replace_existing = True,
    )

    scheduler.start()
    log.info("Scheduler started — Indian market jobs active")


def stop_scheduler():
    scheduler.shutdown()
    log.info("Scheduler stopped")