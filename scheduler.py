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


async def job_indian_orb_setup():
    try:
        from engines.indian.data import is_orb_ready
        if not is_orb_ready():
            return
        from engines.indian.scanner import setup_orb
        result = setup_orb()
        if result:
            log.info("Indian ORB setup: %s", {k: f"{v['high']:.2f}-{v['low']:.2f}" for k, v in result.items()})
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
        await track_outcomes()
        log.info("Indian market close: forced outcome check")
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