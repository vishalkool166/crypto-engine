import logging
from config import cfg

log = logging.getLogger(__name__)


def get_current_version() -> str:
    return cfg.SYSTEM_VERSION


def ensure_version_exists() -> str:
    return cfg.SYSTEM_VERSION


def tag_signal(signal_id: int) -> str:
    return cfg.SYSTEM_VERSION


def tag_trade(trade_id: int) -> str:
    return cfg.SYSTEM_VERSION


def create_new_version(reason: str = "", changed_by: str = "system") -> str:
    return cfg.SYSTEM_VERSION


def get_version_history(limit: int = 20) -> list:
    return []


def get_current_version_record() -> dict | None:
    return {"version": cfg.SYSTEM_VERSION}


def get_performance_by_version() -> list:
    return []