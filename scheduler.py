import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from alerts.scanner import scan_all_coins
from trade.manager import trade_manager

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


async def job_scan():
    now = datetime.now(timezone.utc)
    log.info(f"Scheduled scan: {now.strftime('%H:%M:%S')} UTC")
    try:
        await scan_all_coins()
    except Exception as e:
        log.error(f"Scan job error: {e}")


async def job_monitor():
    try:
        await trade_manager.run_health_check_only()
    except Exception as e:
        log.error(f"Monitor job error: {e}")


def get_next_scan_time() -> str:
    now     = datetime.now(timezone.utc)
    minute  = now.minute
    buckets = [0, 15, 30, 45]
    for b in buckets:
        if minute < b:
            return f"{now.hour:02d}:{b:02d} UTC"
    return f"{(now.hour + 1) % 24:02d}:00 UTC"


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
        minute=0,
        second=0,
        microsecond=0
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
        job_monitor,
        trigger=IntervalTrigger(minutes=1),
        id="monitor",
        replace_existing=True
    )

    scheduler.start()
    log.info(
        f"Scheduler started — UTC — "
        f"scan: :00/:15/:30/:45 — "
        f"monitor: 1m — "
        f"next scan: {get_next_scan_time()}"
    )


def stop_scheduler():
    scheduler.shutdown()
    log.info("Scheduler stopped")