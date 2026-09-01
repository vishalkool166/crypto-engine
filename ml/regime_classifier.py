import logging
log = logging.getLogger(__name__)


def get_regime_performance(min_trades: int = 5) -> dict:
    return {}


def get_regime_recommendations() -> list:
    return []


def classify_current_regime() -> dict:
    return {"regime": "unknown", "action": "normal", "size_mult": 1.0}