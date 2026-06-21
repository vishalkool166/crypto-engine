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


async def job_morning_briefing():
    try:
        from alerts.briefing import send_morning_briefing
        await send_morning_briefing()
    except Exception as e:
        log.error(f"Morning briefing error: {e}")


async def job_ml_check():
    try:
        from ml.eligibility import check_and_train_if_ready
        check_and_train_if_ready()
    except Exception as e:
        log.error(f"ML check job error: {e}")


async def job_engagement_update():
    try:
        from content.publisher import update_all_engagement
        await update_all_engagement()
    except Exception as e:
        log.error(f"Engagement update job error: {e}")


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
        hour=(now.hour + 1) % 24,
        minute=0, second=0, microsecond=0
    )
    return int(next_hour.timestamp() * 1000)


def start_scheduler():
    scheduler.add_job(
        job_scan,
        trigger=CronTrigger(minute="0,15,30,45", timezone="UTC"),
        id="scan",
        replace_existing=True
    )

    scheduler.add_job(
        job_morning_briefing,
        trigger=CronTrigger(hour=2, minute=30, timezone="UTC"),
        id="morning_briefing",
        replace_existing=True
    )

    scheduler.add_job(
        job_ml_check,
        trigger=IntervalTrigger(hours=1),
        id="ml_check",
        replace_existing=True
    )

    scheduler.add_job(
        job_engagement_update,
        trigger=IntervalTrigger(hours=6),
        id="engagement_update",
        replace_existing=True
    )

    scheduler.start()
    log.info(
        f"Scheduler started — "
        f"scan::00/:15/:30/:45 — "
        f"ml_check:1h — "
        f"engagement:6h — "
        f"next scan:{get_next_scan_time()}"
    )


def stop_scheduler():
    scheduler.shutdown()
    log.info("Scheduler stopped")