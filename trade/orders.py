import ccxt
import logging
import time
import json
import os
from datetime import datetime
from config import cfg

log = logging.getLogger(__name__)

QUANTITY_PRECISION = {
    "BTC":  3, "ETH":  3, "BNB":  2, "SOL":  2,
    "XRP":  1, "ADA":  1, "AVAX": 2, "LINK": 2,
    "DOT":  1, "DOGE": 1, "LTC":  3, "ATOM": 2, "POL": 1
}

MIN_NOTIONAL = {
    "BTC":  5.0, "ETH":  5.0, "BNB":  5.0, "SOL":  5.0,
    "XRP":  5.0, "ADA":  5.0, "AVAX": 5.0, "LINK": 5.0,
    "DOT":  5.0, "DOGE": 5.0, "LTC":  5.0, "ATOM": 5.0, "POL": 5.0
}

TAKER_FEE = 0.0006


class PaperOrderStore:

    STORE_FILE = "database/paper_orders.json"

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
            else:
                log.info("No paper orders file found — starting fresh")
        except Exception as e:
            log.error(f"Paper store load error: {e}")
            self._orders  = {}
            self._counter = 1000

    def _save(self):
        try:
            os.makedirs("database", exist_ok=True)
            with open(self.STORE_FILE, "w") as f:
                json.dump({"orders": self._orders, "counter": self._counter}, f, indent=2)
        except Exception as e:
            log.error(f"Paper store save error: {e}")

    def create_order(
        self,
        coin:       str,
        order_type: str,
        side:       str,
        quantity:   float,
        price:      float = None,
        stop_price: float = None,
        label:      str   = ""
    ) -> dict:
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
        log.info(
            f"[PAPER] Order created: id:{order_id} {coin} "
            f"{order_type} {side} qty:{quantity} "
            f"stop:{stop_price} {label}"
        )
        return order

    def get_order(self, order_id: str) -> dict:
        return self._orders.get(str(order_id))

    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(str(order_id))
        if order:
            order["status"] = "cancelled"
            self._save()
            log.info(f"[PAPER] Order cancelled: {order_id}")
            return True
        return False

    def fill_order(self, order_id: str, fill_price: float) -> bool:
        order = self._orders.get(str(order_id))
        if order and order["status"] == "open":
            order["status"]  = "closed"
            order["filled"]  = order["quantity"]
            order["average"] = fill_price
            self._save()
            log.info(f"[PAPER] Order filled: {order_id} @ {fill_price}")
            return True
        return False

    def check_trigger(self, order_id: str, current_price: float) -> bool:
        order = self._orders.get(str(order_id))
        if not order or order["status"] != "open":
            return False

        stop = order.get("stop_price")
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


def with_retry(fn, retries=3, delay=2):
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except ccxt.NetworkError as e:
            log.warning(f"Network error attempt {attempt}/{retries}: {e}")
            if attempt < retries:
                time.sleep(delay)
        except ccxt.ExchangeError as e:
            log.error(f"Exchange error: {e}")
            return None
        except Exception as e:
            log.error(f"Unexpected error attempt {attempt}: {e}")
            if attempt < retries:
                time.sleep(delay)
    log.error(f"All {retries} attempts failed")
    return None


def set_leverage(coin: str, leverage: int) -> bool:
    log.info(f"[PAPER] Leverage set: {coin} {leverage}x")
    return True


def place_market_order(coin: str, direction: str, quantity: float) -> dict:
    side    = "buy" if direction == "LONG" else "sell"
    current = get_current_price(coin)

    if not current:
        log.error(f"[PAPER] Cannot get price: {coin}")
        return None

    notional  = quantity * current
    entry_fee = notional * TAKER_FEE

    order = paper_store.create_order(
        coin=coin, order_type="MARKET",
        side=side, quantity=quantity,
        price=current, label="ENTRY"
    )
    paper_store.fill_order(order["id"], current)
    order["fee"] = entry_fee

    log.info(
        f"[PAPER] Market order filled: {coin} {side} "
        f"qty:{quantity} @ {current} fee:${entry_fee:.4f}"
    )
    return order


def place_sl_order(coin: str, direction: str, quantity: float, sl_price: float) -> dict:
    side  = "sell" if direction == "LONG" else "buy"
    order = paper_store.create_order(
        coin=coin, order_type="STOP_MARKET",
        side=side, quantity=quantity,
        stop_price=sl_price, label="SL"
    )
    log.info(f"[PAPER] SL placed: {coin} @ {sl_price} id:{order['id']}")
    return order


def place_tp_order(
    coin:      str,
    direction: str,
    quantity:  float,
    tp_price:  float,
    label:     str = "TP"
) -> dict:
    side  = "sell" if direction == "LONG" else "buy"
    order = paper_store.create_order(
        coin=coin, order_type="TAKE_PROFIT_MARKET",
        side=side, quantity=quantity,
        stop_price=tp_price, label=label
    )
    log.info(f"[PAPER] {label} placed: {coin} @ {tp_price} id:{order['id']}")
    return order


def cancel_order(coin: str, order_id: str) -> bool:
    result = paper_store.cancel_order(str(order_id))
    if result:
        log.info(f"[PAPER] Order cancelled: {coin} {order_id}")
    return result


def get_order_status(coin: str, order_id: str) -> dict:
    order = paper_store.get_order(str(order_id))

    if not order:
        log.warning(f"[PAPER] Order not found: {order_id}")
        return None

    if order["status"] == "closed":
        return {"id": order["id"], "status": "closed", "filled": order["quantity"], "price": order["average"]}

    if order["status"] == "cancelled":
        return {"id": order["id"], "status": "cancelled", "filled": 0, "price": None}

    current = get_current_price(coin)
    if not current:
        return {"id": order["id"], "status": "open", "filled": 0, "price": None}

    triggered = paper_store.check_trigger(str(order_id), current)

    if triggered:
        fill_price = order["stop_price"]
        notional   = order["quantity"] * fill_price
        exit_fee   = notional * TAKER_FEE

        paper_store.fill_order(str(order_id), fill_price)
        order["fee"] = exit_fee

        log.info(
            f"[PAPER] Stop triggered: {coin} {order.get('label', '')} "
            f"@ {fill_price} fee:${exit_fee:.4f} (current: {current})"
        )
        return {"id": order["id"], "status": "closed", "filled": order["quantity"], "price": fill_price, "fee": exit_fee}

    return {"id": order["id"], "status": "open", "filled": 0, "price": None}


def get_current_price(coin: str) -> float:
    result = with_retry(lambda: exchange.fetch_ticker(f"{coin}/USDT"))
    if result:
        return float(result["last"])
    return 0.0


def close_position_market(coin: str, direction: str, quantity: float) -> dict:
    side    = "sell" if direction == "LONG" else "buy"
    current = get_current_price(coin)

    if not current:
        log.error(f"[PAPER] Cannot get price for close: {coin}")
        return None

    notional = quantity * current
    exit_fee = notional * TAKER_FEE

    order = paper_store.create_order(
        coin=coin, order_type="MARKET",
        side=side, quantity=quantity,
        price=current, label="CLOSE"
    )
    paper_store.fill_order(order["id"], current)
    order["fee"] = exit_fee

    log.info(
        f"[PAPER] Position closed: {coin} {side} "
        f"qty:{quantity} @ {current} fee:${exit_fee:.4f}"
    )
    return order


def calculate_quantity(coin: str, pos_size: float, price: float) -> float:
    if price <= 0:
        log.error(f"Invalid price for {coin}: {price}")
        return 0.0

    precision    = QUANTITY_PRECISION.get(coin, 2)
    min_notional = MIN_NOTIONAL.get(coin, 5.0)

    qty      = round(pos_size / price, precision)
    notional = qty * price

    if notional < min_notional:
        log.warning(
            f"Notional ${notional:.4f} below minimum "
            f"${min_notional} for {coin} — adjusting"
        )
        qty      = round(min_notional / price, precision)
        notional = qty * price
        log.info(f"Adjusted qty: {qty} notional: ${notional:.4f}")

    if qty <= 0:
        log.error(f"Quantity zero after adjustment: {coin}")
        return 0.0

    log.info(
        f"[PAPER] Quantity: {coin} size:${pos_size:.4f} "
        f"price:{price} qty:{qty} "
        f"notional:${notional:.4f} precision:{precision}"
    )
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