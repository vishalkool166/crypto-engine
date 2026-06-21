import logging
import redis as redis_lib
from config import cfg

log = logging.getLogger(__name__)

_redis_client = None


def get_redis() -> redis_lib.Redis | None:
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    try:
        client = redis_lib.from_url(
            cfg.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3
        )
        client.ping()
        _redis_client = client
        log.info(f"Redis connected: {cfg.REDIS_URL}")
        return _redis_client
    except Exception as e:
        log.error(f"Redis connection failed: {e}")
        return None