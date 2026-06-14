import ccxt
import logging
import json
import os
import threading
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import cfg

log = logging.getLogger(__name__)

TAKER_FEE         = 0.0006
_precision_cache: dict = {}
_store_lock       = threading.Lock()

_retry_policy = dict(
    stop    = stop_after_attempt(3),
    wait    = wait_exponential(multiplier=2, min=2, max=16),
    retry   = retry_if_exception_type(ccxt.NetworkError),
    reraise = True
)


def _get_live_executor():
    from trade.live_executor import live_executor
    return live_executor


class PaperOrderStore:

    STORE_FILE  = "database/paper_orders.json"
    BACKUP_FILE = "database/paper_orders.backup.json"

    def __init__(self):
        self._orders:  dict = {}
        self._counter: int  = 1000
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.STORE_FILE):
                with open(self.STORE_FILE, "r") as f:
                    data = json.load(f)
                    self._orders  = data.get("orders", {})
                    self._counter = data.get("counter", 1000)
                log.info(f"Paper orders loaded: {len(self._orders)} orders")
                return
        except Exception as e:
            log.error(f"Paper store load error: {e} — attempting backup restore")

        try:
            if os.path.exists(self.BACKUP_FILE):
                with open(self.BACKUP_FILE, "r") as f:
                    data = json.load(f)
                    self._orders  = data.get("orders", {})
                    self._counter = data.get("counter", 1000)
                log.info(f"Paper orders restored from backup: {len(self._orders)} orders")
                self._save()
                return
        except Exception as e:
            log.error(f"Backup restore failed: {e}")

        self._orders  = {}
        self._counter = 1000

    def _save(self):
        with _store_lock:
            try:
                os.makedirs("database", exist_ok=True)
                data = {"orders": self._orders, "counter": self._counter}
                tmp  = self.STORE_FILE + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(data, f, indent=2)
                os.replace(tmp, self.STORE_FILE)
                import shutil
                shutil.copy2(self.STORE_FILE, self.BACKUP_FILE)
            except Exception as e:
                log.error(f"Paper store save error: {e}")

    def _place_order(self, coin, order_type, side, quantity,
                     price=None, stop_price=None, label="") -> dict:
        order_id      = str(self._counter)
        self._counter += 1
        order = {
            "id":         order_id,
            "coin":       coin,
            "type":       order_type,
            "side":       side,
            "quantity":   quantity,
            "price":      price,
            "stop_price": stop_price,
            "status":     "open",
            "filled":     0.0,
            "average":    price,
            "label":      label,
            "created_at": datetime.utcnow().isoformat()
        }
        self._orders[order_id] = order
        self._save()
        log.info(f"[PAPER] Order: id:{order_id} {coin} {order_type} {side} qty:{quantity} stop:{stop_price} {label}")
        return order

    def create_order(self, coin, order_type, side, quantity,
                     price=None, stop_price=None, label="") -> dict:
        return self._place_order(coin, order_type, side, quantity, price, stop_price, label)

    def get_order(self, order_id: str) -> dict:
        return self._orders.get(str(order_id))

    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(str(order_id))
        if order:
            order["status"] = "cancelled"
            self._save()
            return True
        return False

    def fill_order(self, order_id: str, fill_price: float) -> bool:
        order = self._orders.get(str(order_id))
        if order and order["status"] == "open":
            order["status"]  = "closed"
            order["filled"]  = order["quantity"]
            order["average"] = fill_price
            self._save()
            return True
        return False

    def check_trigger(self, order_id: str, current_price: float) -> bool:
        order = self._orders.get(str(order_id))
        if not order or order["status"] != "open":
            return False
        stop  = order.get("stop_price")
        if not stop:
            return False
        side  = order["side"]
        label = order.get("label", "")
        if side == "sell":
            return current_price <= stop if ("SL" in label or "STOP" in label) else current_price >= stop
        elif side == "buy":
            return current_price >= stop if ("SL" in label or "STOP" in label) else current_price <= stop
        return False

    def get_all_open(self) -> list:
        return [o for o in self._orders.values() if o["status"] == "open"]

    def get_all(self) -> list:
        return list(self._orders.values())


paper_store = PaperOrderStore()


def _get_exchange():
    return ccxt.binance({
        "apiKey": cfg.BINANCE_API_KEY,
        "secret": cfg.BINANCE_SECRET,
        "options": {"defaultType": "future"}
    })

exchange = _get_exchange()


@retry(**_retry_policy)
def _fetch_ticker(coin: str) -> dict:
    return exchange.fetch_ticker(f"{coin}/USDT")


def _get_precision_from_exchange(coin: str) -> tuple:
    if coin in _precision_cache:
        return _precision_cache[coin]
    try:
        markets = exchange.load_markets()
        symbol  = f"{coin}/USDT"
        if symbol in markets:
            m        = markets[symbol]
            qty_prec = int(m.get("precision", {}).get("amount", 2) or 2)
            min_not  = float(m.get("limits", {}).get("cost", {}).get("min", 5.0) or 5.0)
            _precision_cache[coin] = (qty_prec, min_not)
            return qty_prec, min_not
    except Exception as e:
        log.warning(f"Precision fetch failed for {coin}: {e}")
    fallback = (2, 5.0)
    _precision_cache[coin] = fallback
    return fallback


def set_leverage(coin: str, leverage: int) -> bool:
    if cfg.PAPER_TRADING:
        log.info(f"[PAPER] Leverage set: {coin} {leverage}x")
        return True
    return _get_live_executor().set_leverage(coin, leverage)


def _ensure_isolated_margin(coin: str):
    if cfg.PAPER_TRADING:
        return
    _get_live_executor().ensure_isolated(coin)


def place_market_order(coin: str, direction: str, quantity: float) -> dict:
    if cfg.PAPER_TRADING:
        side    = "buy" if direction == "LONG" else "sell"
        current = get_current_price(coin)
        if not current:
            log.error(f"[PAPER] Cannot get price: {coin}")
            return None
        order = paper_store.create_order(
            coin=coin, order_type="MARKET",
            side=side, quantity=quantity,
            price=current, label="ENTRY"
        )
        paper_store.fill_order(order["id"], current)
        order["fee"] = quantity * current * TAKER_FEE
        return order

    return _get_live_executor().place_market(coin, direction, quantity)


def place_sl_order(coin: str, direction: str, quantity: float, sl_price: float) -> dict:
    if cfg.PAPER_TRADING:
        side  = "sell" if direction == "LONG" else "buy"
        order = paper_store.create_order(
            coin=coin, order_type="STOP_MARKET",
            side=side, quantity=quantity,
            stop_price=sl_price, label="SL"
        )
        log.info(f"[PAPER] SL placed: {coin} @ {sl_price} id:{order['id']}")
        return order

    return _get_live_executor().place_sl(coin, direction, quantity, sl_price)


def place_tp_order(coin: str, direction: str, quantity: float,
                   tp_price: float, label: str = "TP") -> dict:
    if cfg.PAPER_TRADING:
        side  = "sell" if direction == "LONG" else "buy"
        order = paper_store.create_order(
            coin=coin, order_type="TAKE_PROFIT_MARKET",
            side=side, quantity=quantity,
            stop_price=tp_price, label=label
        )
        log.info(f"[PAPER] {label} placed: {coin} @ {tp_price} id:{order['id']}")
        return order

    return _get_live_executor().place_tp(coin, direction, quantity, tp_price, label)


def cancel_order(coin: str, order_id: str) -> bool:
    paper_order = paper_store.get_order(str(order_id))
    if paper_order:
        result = paper_store.cancel_order(str(order_id))
        if result:
            log.info(f"[PAPER] Order cancelled: {coin} {order_id}")
        return result

    if cfg.PAPER_TRADING:
        return False

    return _get_live_executor().cancel(coin, order_id)


def get_order_status(coin: str, order_id: str) -> dict:
    paper_order = paper_store.get_order(str(order_id))
    if paper_order:
        if paper_order["status"] == "closed":
            return {"id": paper_order["id"], "status": "closed", "filled": paper_order["quantity"], "price": paper_order["average"]}

        if paper_order["status"] == "cancelled":
            return {"id": paper_order["id"], "status": "cancelled", "filled": 0, "price": None}

        current = get_current_price(coin)
        if not current:
            return {"id": paper_order["id"], "status": "open", "filled": 0, "price": None}

        triggered = paper_store.check_trigger(str(order_id), current)
        if triggered:
            fill_price = paper_order["stop_price"]
            paper_store.fill_order(str(order_id), fill_price)
            log.info(f"[PAPER] Stop triggered: {coin} {paper_order.get('label','')} @ {fill_price}")
            return {"id": paper_order["id"], "status": "closed", "filled": paper_order["quantity"], "price": fill_price}

        return {"id": paper_order["id"], "status": "open", "filled": 0, "price": None}

    if cfg.PAPER_TRADING:
        log.warning(f"[PAPER] Order not found: {order_id}")
        return None

    return _get_live_executor().get_status(coin, order_id)


def get_current_price(coin: str) -> float:
    try:
        result = _fetch_ticker(coin)
        return float(result["last"])
    except Exception as e:
        log.error(f"Price fetch failed {coin}: {e}")
        return 0.0


def close_position_market(coin: str, direction: str, quantity: float) -> dict:
    if cfg.PAPER_TRADING:
        side    = "sell" if direction == "LONG" else "buy"
        current = get_current_price(coin)
        if not current:
            log.error(f"[PAPER] Cannot get price for close: {coin}")
            return None
        order = paper_store.create_order(
            coin=coin, order_type="MARKET",
            side=side, quantity=quantity,
            price=current, label="CLOSE"
        )
        paper_store.fill_order(order["id"], current)
        order["fee"] = quantity * current * TAKER_FEE
        return order

    return _get_live_executor().place_market(coin, direction, quantity)


def calculate_quantity(coin: str, pos_size: float, price: float) -> float:
    if price <= 0:
        log.error(f"Invalid price for {coin}: {price}")
        return 0.0

    precision, min_notional = _get_precision_from_exchange(coin)

    qty      = round(pos_size / price, precision)
    notional = qty * price

    if notional < min_notional:
        qty      = round(min_notional / price, precision)
        notional = qty * price
        log.info(f"Adjusted qty for min notional: {coin} qty:{qty} notional:${notional:.4f}")

    if qty <= 0:
        log.error(f"Quantity zero after adjustment: {coin}")
        return 0.0

    return qty


def get_paper_status() -> dict:
    open_orders = paper_store.get_all_open()
    all_orders  = paper_store.get_all()
    return {
        "mode":         "PAPER",
        "open_orders":  len(open_orders),
        "total_orders": len(all_orders),
        "orders":       open_orders
    }