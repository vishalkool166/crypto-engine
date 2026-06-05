from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from alerts.scanner import scan_all_coins
from trade.manager import trade_manager
from data.cache import cache
from datetime import datetime, timezone
import logging

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


# ═══════════════════════════════════════════════════════
# SCAN JOB
# ═══════════════════════════════════════════════════════
async def job_scan():
    now = datetime.now(timezone.utc)
    log.info(
        f"Scheduled scan running: "
        f"{now.strftime('%H:%M:%S')} UTC"
    )
    try:
        await scan_all_coins()
    except Exception as e:
        log.error(f"Scan job error: {e}")


# ═══════════════════════════════════════════════════════
# MONITOR JOB
# ═══════════════════════════════════════════════════════
async def job_monitor():
    try:
        await trade_manager.monitor_trade()
    except Exception as e:
        log.error(f"Monitor job error: {e}")


# ═══════════════════════════════════════════════════════
# CACHE CLEANUP JOB
# ═══════════════════════════════════════════════════════
async def job_cache_cleanup():
    log.info("Cache cleanup running")


# ═══════════════════════════════════════════════════════
# GET NEXT SYNC TIME
# Returns human readable next scan time
# ═══════════════════════════════════════════════════════
def get_next_scan_time() -> str:
    now     = datetime.now(timezone.utc)
    minute  = now.minute
    # Next :00, :15, :30, :45
    buckets = [0, 15, 30, 45]
    for b in buckets:
        if minute < b:
            return (
                f"{now.hour:02d}:{b:02d} UTC"
            )
    # Next hour :00
    next_hour = (now.hour + 1) % 24
    return f"{next_hour:02d}:00 UTC"


# ═══════════════════════════════════════════════════════
# START SCHEDULER
# ══════════════════════════════════════════════════════
# FIX — Timestamped sync scanning
# Uses CronTrigger at :00 :15 :30 :45
# every hour every day
# All devices sync to same clock
# Manual scan does NOT reset timer
# Next auto scan always at next quarter hour
# ═══════════════════════════════════════════════════════
def start_scheduler():

    # ── SCAN — fixed clock times ──
    # Runs at :00 :15 :30 :45 of every hour
    scheduler.add_job(
        job_scan,
        trigger=CronTrigger(
            minute="0,15,30,45",
            timezone="UTC"
        ),
        id="scan",
        replace_existing=True
    )

    # ── MONITOR — every 1 minute ──
    # Unchanged — needs frequent checks
    scheduler.add_job(
        job_monitor,
        trigger=IntervalTrigger(minutes=1),
        id="monitor",
        replace_existing=True
    )

    # ── CACHE CLEANUP — every 20 minutes ──
    scheduler.add_job(
        job_cache_cleanup,
        trigger=IntervalTrigger(minutes=20),
        id="cache_cleanup",
        replace_existing=True
    )

    scheduler.start()

    next_scan = get_next_scan_time()
    log.info(
        f"Scheduler started — "
        f"scan: :00/:15/:30/:45 UTC (synced) "
        f"monitor: 1m "
        f"next scan: {next_scan}"
    )


def stop_scheduler():
    scheduler.shutdown()
    log.info("Scheduler stopped")