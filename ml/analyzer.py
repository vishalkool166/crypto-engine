import logging
log = logging.getLogger(__name__)


def run() -> dict:
    return {"status": "disabled", "recommendations": []}


def get_pending_recommendations() -> list:
    return []


def get_approved_recommendations() -> list:
    return []


def approve_recommendation(rec_id: int, approved_by: str = "human") -> bool:
    return False


def reject_recommendation(rec_id: int, reason: str = "") -> bool:
    return False