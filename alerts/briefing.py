import logging
from datetime import datetime, timezone, timedelta
from data.cache import cache
from config import cfg

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


async def send_morning_briefing():
    try:
        from alerts.telegram.commands.content import cmd_brief
        await cmd_brief()
        log.info("Morning briefing sent")
    except Exception as e:
        log.error("Morning briefing error: %s", e)


async def send_evening_briefing():
    try:
        from alerts.telegram.commands.content import cmd_brief
        await cmd_brief()
        log.info("Evening briefing sent")
    except Exception as e:
        log.error("Evening briefing error: %s", e)