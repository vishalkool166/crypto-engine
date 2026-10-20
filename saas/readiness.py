"""Small, sanitized dependency readiness probe; never performs broker actions."""
from collections.abc import Callable


def _database_probe() -> bool:
    from sqlalchemy import text
    from database import get_session
    with get_session() as db:
        db.execute(text('SELECT 1'))
    return True


def _redis_probe() -> bool:
    from redis_client import get_redis
    redis = get_redis()
    return bool(redis and redis.ping())


def readiness_status(
    database_probe: Callable[[], bool] | None = None,
    redis_probe: Callable[[], bool] | None = None,
) -> dict:
    """Return only dependency names and up/down state; never expose exceptions."""
    probes = {
        'database': database_probe or _database_probe,
        'redis': redis_probe or _redis_probe,
    }
    checks = {}
    for name, probe in probes.items():
        try:
            checks[name] = 'up' if probe() else 'down'
        except Exception:
            checks[name] = 'down'
    ready = all(value == 'up' for value in checks.values())
    return {'status': 'ready' if ready else 'degraded', 'checks': checks}
