import logging
log = logging.getLogger(__name__)


def run() -> dict:
    return {"status": "disabled", "recommendations": []}


def get_current_weights() -> dict:
    return {
        "sweep":         0.25,
        "zone":          0.25,
        "structure":     0.20,
        "btc_alignment": 0.15,
        "regime":        0.15,
    }


def cleanup_old_snapshots(keep_per_trade: int = 200) -> int:
    return 0