import json
import time
import logging
from datetime import datetime, timezone
from redis_client import get_redis
from config import cfg

log = logging.getLogger(__name__)

HE = cfg.HYBRID_ENGINE


def _key(coin: str) -> str:
    return f"scalp_state:{coin}"


def _outcome_key(coin: str) -> str:
    return f"coin_outcome:{coin}"


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


def set_last_outcome(coin: str, outcome: str, pnl: float = 0.0) -> None:
    try:
        r = get_redis()
        if r:
            r.setex(
                _outcome_key(coin),
                86400,
                json.dumps({"outcome": outcome, "pnl": pnl, "recorded_at": time.time()})
            )
        try:
            from database import SessionLocal, CoinLastOutcome
            db = SessionLocal()
            try:
                existing = db.query(CoinLastOutcome).filter(CoinLastOutcome.coin == coin).first()
                if existing:
                    existing.outcome     = outcome
                    existing.pnl         = pnl
                    existing.recorded_at = datetime.now(timezone.utc)
                else:
                    db.add(CoinLastOutcome(
                        coin        = coin,
                        outcome     = outcome,
                        pnl         = pnl,
                        recorded_at = datetime.now(timezone.utc),
                    ))
                db.commit()
            finally:
                db.close()
        except Exception as e:
            log.warning("set_last_outcome db write %s: %s", coin, e)
    except Exception as e:
        log.warning("set_last_outcome %s: %s", coin, e)


def get_last_outcome(coin: str) -> dict | None:
    try:
        r = get_redis()
        if r:
            raw = r.get(_outcome_key(coin))
            if raw:
                return json.loads(raw)
    except Exception:
        pass
    try:
        from database import SessionLocal, CoinLastOutcome
        db = SessionLocal()
        try:
            row = db.query(CoinLastOutcome).filter(CoinLastOutcome.coin == coin).first()
            if row:
                return {
                    "outcome":     row.outcome,
                    "pnl":         row.pnl,
                    "recorded_at": row.recorded_at.timestamp() if row.recorded_at else 0,
                }
        finally:
            db.close()
    except Exception as e:
        log.warning("get_last_outcome db read %s: %s", coin, e)
    return None


def should_skip_after_loss(coin: str) -> bool:
    from config import get_coin_config
    coin_cfg = get_coin_config(coin)
    if not coin_cfg.get("skip_after_loss", False):
        return False
    last = get_last_outcome(coin)
    if not last:
        return False
    if last.get("outcome") == "loss":
        age_hours = (time.time() - last.get("recorded_at", 0)) / 3600
        if age_hours < 48:
            return True
    return False