from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from alerts.scanner import scan_all_coins
from trade.manager import trade_manager
from data.cache import cache
from datetime import datetime
import logging

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def job_scan():
    log.info("Running scan...")
    try:
        await scan_all_coins()
    except Exception as e:
        log.error(f"Scan job error: {e}")

async def job_monitor():
    try:
        await trade_manager.monitor_trade()
    except Exception as e:
        log.error(f"Monitor job error: {e}")

async def job_cache_cleanup():
    log.info("Cache cleanup")

def start_scheduler():
    scheduler.add_job(
        job_scan,
        trigger=IntervalTrigger(minutes=15),
        id="scan",
        replace_existing=True,
        next_run_time=datetime.now()
    )
    scheduler.add_job(
        job_monitor,
        trigger=IntervalTrigger(minutes=1),
        id="monitor",
        replace_existing=True
    )
    scheduler.add_job(
        job_cache_cleanup,
        trigger=IntervalTrigger(minutes=10),
        id="cache_cleanup",
        replace_existing=True
    )
    scheduler.start()
    log.info(
        "Scheduler started — "
        "scan:15m(immediate) "
        "monitor:1m "
        "telegram:webhook"
    )

def stop_scheduler():
    scheduler.shutdown()
    log.info("Scheduler stopped")