import logging
log = logging.getLogger(__name__)


async def run_health_checks():
    pass


def get_health_from_redis(coin: str) -> dict | None:
    return None


def clear_health_state(coin: str):
    pass