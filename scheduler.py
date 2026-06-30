import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from alerts.scanner import scan_all_coins

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

IST = timezone(timedelta(hours=5, minutes=30))


async def job_scan():
    now = datetime.now(timezone.utc)
    log.info(f"Scheduled scan: {now.strftime('%H:%M:%S')} UTC")
    try:
        await scan_all_coins()
    except Exception as e:
        log.error(f"Scan job error: {e}")


async def job_monitor():
    try:
        from trade.monitor import run_monitor_cycle
        await run_monitor_cycle()
    except Exception as e:
        log.error(f"Monitor job error: {e}")


async def job_ml_check():
    try:
        from ml.eligibility import check_and_train_if_ready
        check_and_train_if_ready()
    except Exception as e:
        log.error(f"ML check job error: {e}")


async def job_health_check():
    try:
        from trade.health_monitor import run_health_checks
        await run_health_checks()
    except Exception as e:
        log.error(f"Health check job error: {e}")


async def job_purge_content():
    try:
        from content.approval_flow import purge_old_content
        purge_old_content(days=7)
    except Exception as e:
        log.error(f"Content purge job error: {e}")


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
        job_scan,
        trigger          = CronTrigger(minute="0,15,30,45", timezone="UTC"),
        id               = "scan",
        replace_existing = True
    )

    scheduler.add_job(
        job_monitor,
        trigger          = IntervalTrigger(seconds=30),
        id               = "monitor",
        replace_existing = True
    )

    scheduler.add_job(
        job_ml_check,
        trigger          = IntervalTrigger(hours=1),
        id               = "ml_check",
        replace_existing = True
    )

    scheduler.add_job(
        job_health_check,
        trigger          = IntervalTrigger(minutes=1),
        id               = "health_check",
        replace_existing = True
    )

    scheduler.add_job(
        job_purge_content,
        trigger          = CronTrigger(hour=3, minute=0, timezone="UTC"),
        id               = "purge_content",
        replace_existing = True
    )

    scheduler.start()
    log.info(
        f"Scheduler started — "
        f"scan::00/:15/:30/:45 — "
        f"monitor:30s — "
        f"health:1m — "
        f"ml:1h — "
        f"purge:03:00 UTC — "
        f"next scan:{get_next_scan_time()}"
    )


def stop_scheduler():
    scheduler.shutdown()
    log.info("Scheduler stopped")