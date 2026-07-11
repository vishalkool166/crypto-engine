import json
import time
import logging
from transitions import Machine
from config import cfg

log = logging.getLogger(__name__)

STATES = [
    "no_bias",
    "bias_defined",
    "zone_active",
    "signal_ready",
    "trade_active",
    "cooldown",
]

TRANSITIONS = [
    {
        "trigger":    "bias_detected",
        "source":     "no_bias",
        "dest":       "bias_defined",
        "conditions": "is_bias_valid",
        "after":      "on_bias_defined",
    },
    {
        "trigger":    "zone_found",
        "source":     "bias_defined",
        "dest":       "zone_active",
        "conditions": "is_zone_valid",
        "after":      "on_zone_active",
    },
    {
        "trigger":    "trigger_confirmed",
        "source":     "zone_active",
        "dest":       "signal_ready",
        "conditions": "is_trigger_valid",
        "after":      "on_signal_ready",
    },
    {
        "trigger":    "trade_opened",
        "source":     "signal_ready",
        "dest":       "trade_active",
        "after":      "on_trade_active",
    },
    {
        "trigger":    "trade_closed",
        "source":     "trade_active",
        "dest":       "cooldown",
        "after":      "on_cooldown",
    },
    {
        "trigger":    "zone_invalidated",
        "source":     "zone_active",
        "dest":       "bias_defined",
        "after":      "on_zone_invalidated",
    },
    {
        "trigger":    "bias_lost",
        "source":     ["bias_defined", "zone_active", "signal_ready"],
        "dest":       "no_bias",
        "after":      "on_reset",
    },
    {
        "trigger":    "cooldown_expired",
        "source":     "cooldown",
        "dest":       "no_bias",
        "after":      "on_reset",
    },
    {
        "trigger":    "reset",
        "source":     "*",
        "dest":       "no_bias",
        "after":      "on_reset",
    },
]


class CoinMachine:

    def __init__(self, coin: str, context: dict = None):
        self.coin         = coin
        self.context      = context or {}
        self.cooldown_at  = None

        self.machine = Machine(
            model                   = self,
            states                  = STATES,
            transitions             = TRANSITIONS,
            initial                 = "no_bias",
            ignore_invalid_triggers = True,
            auto_transitions        = False,
        )

    def is_bias_valid(self) -> bool:
        return (
            self.context.get("direction") in ("LONG", "SHORT") and
            self.context.get("slope_defined", False) and
            self.context.get("sweep_detected", False)
        )

    def is_zone_valid(self) -> bool:
        zone = self.context.get("zone")
        if not zone:
            return False
        return (
            zone.get("distance_pct", 99) <= zone.get("max_distance", 3.0) and
            zone.get("touch_count", 99)  <= cfg.SIGNAL_ENGINE["zone_max_touches"]
        )

    def is_trigger_valid(self) -> bool:
        return (
            self.context.get("trigger_pattern") is not None and
            self.context.get("rr_valid", False) and
            self.context.get("entry_price") is not None and
            self.context.get("sl") is not None
        )

    def on_bias_defined(self):
        log.info(
            "%s → bias_defined | direction:%s strength:%s sweep_age:%.1fh",
            self.coin,
            self.context.get("direction"),
            self.context.get("strength"),
            self.context.get("sweep_age_hours") or 0,
        )

    def on_zone_active(self):
        zone = self.context.get("zone", {})
        log.info(
            "%s → zone_active | %s %s %.4f-%.4f dist:%.2f%%",
            self.coin,
            self.context.get("direction"),
            zone.get("type"),
            zone.get("bottom", 0),
            zone.get("top", 0),
            zone.get("distance_pct", 0),
        )

    def on_signal_ready(self):
        log.info(
            "%s → signal_ready | pattern:%s entry:%s rr:%s",
            self.coin,
            self.context.get("trigger_pattern"),
            self.context.get("entry_price"),
            self.context.get("rr"),
        )

    def on_trade_active(self):
        log.info("%s → trade_active", self.coin)

    def on_cooldown(self):
        self.cooldown_at = time.time()
        log.info(
            "%s → cooldown | %.0fh",
            self.coin,
            cfg.SIGNAL_ENGINE["cooldown_hours"],
        )

    def on_zone_invalidated(self):
        self.context.pop("zone",            None)
        self.context.pop("trigger_pattern", None)
        self.context.pop("entry_price",     None)
        self.context.pop("sl",              None)
        self.context.pop("rr",              None)
        self.context.pop("rr_valid",        None)
        log.info("%s → zone_invalidated → bias_defined", self.coin)

    def on_reset(self):
        self.context     = {}
        self.cooldown_at = None
        log.info("%s → no_bias | reset", self.coin)

    def is_cooldown_expired(self) -> bool:
        if not self.cooldown_at:
            return True
        hours = cfg.SIGNAL_ENGINE["cooldown_hours"]
        return (time.time() - self.cooldown_at) >= hours * 3600


class CoinStateManager:

    def __init__(self):
        self._machines: dict[str, CoinMachine] = {}

    def get(self, coin: str) -> CoinMachine:
        if coin not in self._machines:
            self._machines[coin] = self._load_or_create(coin)
        return self._machines[coin]

    def get_state(self, coin: str) -> str:
        return self.get(coin).state

    def get_context(self, coin: str) -> dict:
        return self.get(coin).context

    def update_context(self, coin: str, updates: dict):
        machine = self.get(coin)
        machine.context.update(updates)
        self._persist(coin)

    def tick_cooldowns(self):
        for coin, machine in self._machines.items():
            if machine.state == "cooldown" and machine.is_cooldown_expired():
                machine.cooldown_expired()
                self._persist(coin)
                log.info("%s cooldown expired → no_bias", coin)

    def snapshot(self) -> dict:
        return {
            coin: {
                "state":   m.state,
                "context": m.context,
            }
            for coin, m in self._machines.items()
        }

    def _load_or_create(self, coin: str) -> CoinMachine:
        saved = self._load(coin)
        if not saved:
            return CoinMachine(coin)

        machine       = CoinMachine(coin, saved.get("context", {}))
        machine.state = saved.get("state", "no_bias")

        if machine.state == "cooldown":
            machine.cooldown_at = saved.get("cooldown_at")

        log.info("%s state restored: %s", coin, machine.state)
        return machine

    def _persist(self, coin: str):
        machine = self._machines.get(coin)
        if not machine:
            return

        data = {
            "state":       machine.state,
            "context":     machine.context,
            "cooldown_at": machine.cooldown_at,
            "updated_at":  time.time(),
        }

        try:
            from redis_client import get_redis
            r = get_redis()
            if r:
                r.setex(
                    f"coin_state:{coin}",
                    int(cfg.SIGNAL_ENGINE["cooldown_hours"] * 2 * 3600),
                    json.dumps(data, default=str),
                )
                return
        except Exception as e:
            log.warning("Redis persist failed %s: %s", coin, e)

        import runtime_state as rs
        states        = rs.get("coin_states") or {}
        states[coin]  = data
        rs.set("coin_states", states)

    def _load(self, coin: str) -> dict | None:
        try:
            from redis_client import get_redis
            r = get_redis()
            if r:
                raw = r.get(f"coin_state:{coin}")
                if raw:
                    return json.loads(raw)
        except Exception as e:
            log.warning("Redis load failed %s: %s", coin, e)

        import runtime_state as rs
        states = rs.get("coin_states") or {}
        return states.get(coin)

    def persist_all(self):
        for coin in self._machines:
            self._persist(coin)


state_manager = CoinStateManager()