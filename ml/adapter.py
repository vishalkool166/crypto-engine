import logging
log = logging.getLogger(__name__)


def run() -> dict:
    return {"status": "disabled", "applied": 0}


def get_adaptation_history(limit: int = 20) -> list:
    return []