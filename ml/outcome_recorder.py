import logging
log = logging.getLogger(__name__)


async def record(trade_id: int) -> bool:
    return True


def get_outcome(trade_id: int) -> dict | None:
    return None