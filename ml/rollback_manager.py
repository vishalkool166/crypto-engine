import logging
log = logging.getLogger(__name__)


def manual_rollback(parameter: str, reason: str = "manual") -> dict:
    return {"success": False, "reason": "adaptation system disabled"}


def get_pending_checkpoints() -> list:
    return []


def check_all_pending() -> list:
    return []