import json
import time
import logging
from redis_client import get_redis
from config import cfg

log = logging.getLogger(__name__)

HE = cfg.HYBRID_ENGINE


def _key(coin: str) -> str:
    return f"scalp_state:{coin}"


def _ttl() -> int:
    return int(HE["coin_cooldown_hours"] * 2 * 3600)


def get(coin: str) -> dict:
    try:
        r = get_redis()
        if r:
            raw = r.get(_key(coin))
            if raw:
                return json.loads(raw)
    except Exception as e:
        log.warning("state.get %s: %s", coin, e)
    return {"coin": coin, "status": "idle", "setup": None, "trade_id": None, "cooldown_until": None}


def save(coin: str, state: dict) -> None:
    try:
        r = get_redis()
        if r:
            r.setex(_key(coin), _ttl(), json.dumps(state, default=str))
    except Exception as e:
        log.warning("state.save %s: %s", coin, e)


def set_idle(coin: str) -> None:
    save(coin, {"coin": coin, "status": "idle", "setup": None, "trade_id": None, "cooldown_until": None})


def set_watching(coin: str, setup: dict) -> None:
    save(coin, {"coin": coin, "status": "watching", "setup": setup, "trade_id": None, "cooldown_until": None})


def set_in_trade(coin: str, trade_id: int, setup: dict) -> None:
    save(coin, {"coin": coin, "status": "in_trade", "setup": setup, "trade_id": trade_id, "cooldown_until": None})


def set_cooldown(coin: str) -> None:
    until = time.time() + HE["coin_cooldown_hours"] * 3600
    save(coin, {"coin": coin, "status": "cooldown", "setup": None, "trade_id": None, "cooldown_until": until})


def is_watching(coin: str) -> bool:
    return get(coin)["status"] == "watching"


def is_in_trade(coin: str) -> bool:
    return get(coin)["status"] == "in_trade"


def is_available(coin: str) -> bool:
    state = get(coin)
    if state["status"] == "cooldown":
        if time.time() >= (state["cooldown_until"] or 0):
            set_idle(coin)
            return True
        return False
    return state["status"] in ("idle", "watching")


def get_watching_coins() -> list:
    return [c for c in cfg.COINS if get(c)["status"] == "watching"]


def get_all_states() -> dict:
    return {c: get(c) for c in cfg.COINS}


def tick_cooldowns() -> None:
    for coin in cfg.COINS:
        is_available(coin)