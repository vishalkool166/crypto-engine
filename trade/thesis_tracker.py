import logging
log = logging.getLogger(__name__)


def create_thesis(*args, **kwargs):
    pass


def get_thesis(trade_id: int):
    return None


def remove_thesis(trade_id: int):
    pass


def get_all_active() -> dict:
    return {}


def get_thesis_summary(trade_id: int) -> dict:
    return {}


def get_pillar_states_json(trade_id: int) -> str:
    return "{}"


def update_snapshot_outcome(trade_id: int, outcome: str, final_pnl: float):
    pass


async def evaluate(trade_id: int, trade: dict):
    pass