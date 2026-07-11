import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

IST = timezone(timedelta(hours=5, minutes=30))


async def job_daily_bias_update():
    log.info("Daily bias update started")
    try:
        from alerts.scanner import run_daily_bias_update
        await run_daily_bias_update()
    except Exception as e:
        log.error("Daily bias update error: %s", e)


async def job_zone_update():
    log.info("Zone update started")
    try:
        from alerts.scanner import run_zone_update
        await run_zone_update()
    except Exception as e:
        log.error("Zone update error: %s", e)


async def job_trigger_check():
    try:
        from alerts.scanner import run_trigger_check
        await run_trigger_check()
    except Exception as e:
        log.error("Trigger check error: %s", e)


async def job_market_data():
    try:
        from alerts.scanner import run_market_data_update
        await run_market_data_update()
    except Exception as e:
        log.error("Market data update error: %s", e)


async def job_monitor():
    try:
        from trade.monitor import run_monitor_cycle
        await run_monitor_cycle()
    except Exception as e:
        log.error("Monitor job error: %s", e)


async def job_ml_check():
    try:
        from ml.eligibility import check_and_train_if_ready
        check_and_train_if_ready()
    except Exception as e:
        log.error("ML check job error: %s", e)


async def job_health_check():
    try:
        from trade.health_monitor import run_health_checks
        await run_health_checks()
    except Exception as e:
        log.error("Health check job error: %s", e)


async def job_purge_content():
    try:
        from content.approval_flow import purge_old_content
        purge_old_content(days=7)
    except Exception as e:
        log.error("Content purge job error: %s", e)


async def job_cooldown_tick():
    try:
        from engines.coin_state import state_manager
        state_manager.tick_cooldowns()
    except Exception as e:
        log.error("Cooldown tick error: %s", e)


def get_next_scan_time() -> str:
    now     = datetime.now(timezone.utc)
    minute  = now.minute
    buckets = [0, 15, 30, 45]
    for b in buckets:
        if minute < b:
            next_utc = now.replace(minute=b, second=0, microsecond=0)
            next_ist = next_utc.astimezone(IST)
            return next_ist.strftime("%I:%M %p IST")
    next_utc = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    next_ist = next_utc.astimezone(IST)
    return next_ist.strftime("%I:%M %p IST")


def get_next_scan_epoch() -> int:
    now     = datetime.now(timezone.utc)
    minute  = now.minute
    buckets = [0, 15, 30, 45]
    for b in buckets:
        if minute < b:
            next_dt = now.replace(minute=b, second=0, microsecond=0)
            return int(next_dt.timestamp() * 1000)
    next_hour = now.replace(
        hour        = (now.hour + 1) % 24,
        minute      = 0,
        second      = 0,
        microsecond = 0
    )
    return int(next_hour.timestamp() * 1000)


def start_scheduler():
    scheduler.add_job(
        job_daily_bias_update,
        trigger          = CronTrigger(hour=0, minute=5, timezone="UTC"),
        id               = "daily_bias",
        replace_existing = True,
    )

    scheduler.add_job(
        job_zone_update,
        trigger          = CronTrigger(hour="0,4,8,12,16,20", minute=5, timezone="UTC"),
        id               = "zone_update",
        replace_existing = True,
    )

    scheduler.add_job(
        job_trigger_check,
        trigger          = CronTrigger(minute="0,15,30,45", timezone="UTC"),
        id               = "trigger_check",
        replace_existing = True,
    )

    scheduler.add_job(
        job_market_data,
        trigger          = CronTrigger(minute="0,15,30,45", timezone="UTC"),
        id               = "market_data",
        replace_existing = True,
    )

    scheduler.add_job(
        job_monitor,
        trigger          = IntervalTrigger(seconds=30),
        id               = "monitor",
        replace_existing = True,
    )

    scheduler.add_job(
        job_ml_check,
        trigger          = IntervalTrigger(hours=1),
        id               = "ml_check",
        replace_existing = True,
    )

    scheduler.add_job(
        job_health_check,
        trigger          = IntervalTrigger(minutes=1),
        id               = "health_check",
        replace_existing = True,
    )

    scheduler.add_job(
        job_purge_content,
        trigger          = CronTrigger(hour=3, minute=0, timezone="UTC"),
        id               = "purge_content",
        replace_existing = True,
    )

    scheduler.add_job(
        job_cooldown_tick,
        trigger          = IntervalTrigger(minutes=30),
        id               = "cooldown_tick",
        replace_existing = True,
    )

    scheduler.start()
    log.info(
        "Scheduler started — "
        "bias:00:05 UTC — "
        "zones:00,04,08,12,16,20:05 UTC — "
        "trigger+market::00/:15/:30/:45 — "
        "monitor:30s — "
        "health:1m — "
        "ml:1h — "
        "cooldown:30m — "
        "purge:03:00 UTC"
    )


def stop_scheduler():
    scheduler.shutdown()
    log.info("Scheduler stopped")