import logging
log = logging.getLogger(__name__)


def get_safety_summary() -> dict:
    return {
        "frozen":             False,
        "changes_this_month": 0,
        "max_changes_month":  0,
        "total_trades":       0,
        "min_trades_required":50,
        "ready_to_adapt":     False,
        "require_approval":   True,
    }