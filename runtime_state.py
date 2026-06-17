import json
import os
import logging
import time
from threading import Lock

log = logging.getLogger(__name__)

STATE_FILE = "runtime_state.json"
_lock      = Lock()

_defaults = {
    "trading_mode":    "paper",
    "last_signal_time": 0,
    "balance_cache":   {"balance": 0.0, "updated_at": 0},
    "tier_config":     {"tier": 1, "risk_pct": 0.05, "max_trades": 1, "leverage": 5},
    "totp_pending":    {},
    "crash_detected":  False,
    "last_shutdown":   "clean",
    "paper_balance":   0.0,
}

_state: dict = {}


def load():
    global _state
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                loaded = json.load(f)
            _state = {**_defaults, **loaded}
            log.info(f"Runtime state loaded: mode={_state['trading_mode']} crash={_state['crash_detected']}")
        else:
            _state = dict(_defaults)
            log.info("No runtime state found — using defaults")
    except Exception as e:
        log.error(f"Runtime state load error: {e} — using defaults")
        _state = dict(_defaults)
    return _state


def save():
    with _lock:
        try:
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(_state, f, indent=2)
            os.replace(tmp, STATE_FILE)
        except Exception as e:
            log.error(f"Runtime state save error: {e}")


def get(key: str, default=None):
    return _state.get(key, default)


def set(key: str, value):
    _state[key] = value
    save()


def get_trading_mode() -> str:
    return _state.get("trading_mode", "paper")


def set_trading_mode(mode: str):
    _state["trading_mode"] = mode
    save()
    log.info(f"Trading mode set: {mode}")


def get_balance_cache() -> dict:
    return _state.get("balance_cache", {"balance": 0.0, "updated_at": 0})


def set_balance_cache(balance: float):
    _state["balance_cache"] = {"balance": balance, "updated_at": time.time()}
    save()


def get_tier_config() -> dict:
    return _state.get("tier_config", _defaults["tier_config"])


def set_tier_config(tier_cfg: dict):
    _state["tier_config"] = tier_cfg
    save()


def get_last_signal_time() -> float:
    return _state.get("last_signal_time", 0)


def set_last_signal_time(t: float):
    _state["last_signal_time"] = t
    save()


def set_totp_pending(chat_id: str, action: str, expires_at: float):
    _state.setdefault("totp_pending", {})
    _state["totp_pending"][str(chat_id)] = {
        "action":     action,
        "expires_at": expires_at
    }
    save()


def get_totp_pending(chat_id: str) -> dict | None:
    pending = _state.get("totp_pending", {})
    entry   = pending.get(str(chat_id))
    if not entry:
        return None
    if time.time() > entry["expires_at"]:
        clear_totp_pending(chat_id)
        return None
    return entry


def clear_totp_pending(chat_id: str):
    _state.setdefault("totp_pending", {})
    _state["totp_pending"].pop(str(chat_id), None)
    save()


def mark_crash():
    _state["crash_detected"] = True
    _state["last_shutdown"]  = "crash"
    save()


def mark_clean_shutdown():
    _state["crash_detected"] = False
    _state["last_shutdown"]  = "clean"
    save()


def was_crash() -> bool:
    return _state.get("crash_detected", False)

def get_paper_balance() -> float:
    return _state.get("paper_balance", 0.0)


def set_paper_balance(balance: float):
    _state["paper_balance"] = balance
    save()


# Load on import
load()