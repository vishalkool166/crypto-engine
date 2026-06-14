import logging
import time
import ccxt
from config import cfg
from database import get_session, AuditLog

log = logging.getLogger(__name__)

exchange = ccxt.binance({
    "apiKey": cfg.BINANCE_API_KEY,
    "secret": cfg.BINANCE_SECRET,
    "options": {"defaultType": "future"}
})


def _retry(fn, retries=3, base_delay=2):
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except ccxt.NetworkError as e:
            log.warning(f"Network error attempt {attempt}/{retries}: {e}")
            if attempt < retries:
                time.sleep(base_delay * (2 ** (attempt - 1)))
        except ccxt.ExchangeError as e:
            log.error(f"Exchange error: {e}")
            return None
        except Exception as e:
            log.error(f"Unexpected error attempt {attempt}: {e}")
            if attempt < retries:
                time.sleep(base_delay * (2 ** (attempt - 1)))
    log.error(f"All {retries} attempts failed")
    return None


class LiveOrderExecutor:

    def place_market(self, coin: str, direction: str, quantity: float) -> dict:
        side   = "buy" if direction == "LONG" else "sell"
        result = _retry(
            lambda: exchange.create_order(
                f"{coin}/USDT", "market", side, quantity,
                params={"reduceOnly": False}
            ),
            retries=3, base_delay=2
        )
        if not result:
            log.error(f"[LIVE] Market order failed: {coin} {side} qty:{quantity}")
            return None

        filled = float(result.get("filled", 0))
        amount = float(result.get("amount", quantity))
        if filled < amount:
            log.warning(f"[LIVE] Partial fill: {coin} filled:{filled} expected:{amount}")
            self._handle_partial_fill(coin, result, filled, amount)

        log.info(f"[LIVE] Market order filled: {coin} {side} qty:{filled} @ {result.get('average')}")
        self._audit(f"market_{side}", coin, f"qty:{filled} avg:{result.get('average')}")
        return result

    def place_sl(self, coin: str, direction: str, quantity: float, sl_price: float) -> dict:
        side   = "sell" if direction == "LONG" else "buy"
        result = _retry(
            lambda: exchange.create_order(
                f"{coin}/USDT", "stop_market", side, quantity,
                params={"stopPrice": sl_price, "reduceOnly": True, "closePosition": False}
            ),
            retries=3, base_delay=2
        )
        if not result:
            log.error(f"[LIVE] SL order failed: {coin} @ {sl_price}")
            return None
        log.info(f"[LIVE] SL placed: {coin} @ {sl_price} id:{result.get('id')}")
        self._audit("place_sl", coin, f"sl:{sl_price} qty:{quantity}")
        return result

    def place_tp(self, coin: str, direction: str, quantity: float,
                 tp_price: float, label: str = "TP") -> dict:
        side   = "sell" if direction == "LONG" else "buy"
        result = _retry(
            lambda: exchange.create_order(
                f"{coin}/USDT", "take_profit_market", side, quantity,
                params={"stopPrice": tp_price, "reduceOnly": True, "closePosition": False}
            ),
            retries=3, base_delay=2
        )
        if not result:
            log.error(f"[LIVE] {label} order failed: {coin} @ {tp_price}")
            return None
        log.info(f"[LIVE] {label} placed: {coin} @ {tp_price} id:{result.get('id')}")
        self._audit(f"place_{label.lower()}", coin, f"tp:{tp_price} qty:{quantity}")
        return result

    def cancel(self, coin: str, order_id: str) -> bool:
        result = _retry(
            lambda: exchange.cancel_order(order_id, f"{coin}/USDT"),
            retries=3, base_delay=2
        )
        if result:
            log.info(f"[LIVE] Order cancelled: {coin} {order_id}")
            return True
        log.error(f"[LIVE] Cancel failed: {coin} {order_id}")
        return False

    def get_status(self, coin: str, order_id: str) -> dict:
        result = _retry(
            lambda: exchange.fetch_order(order_id, f"{coin}/USDT"),
            retries=3, base_delay=2
        )
        if not result:
            return None
        return {
            "id":     result.get("id"),
            "status": result.get("status"),
            "filled": float(result.get("filled", 0)),
            "amount": float(result.get("amount", 0)),
            "price":  float(result.get("average") or result.get("price") or 0)
        }

    def set_leverage(self, coin: str, leverage: int) -> bool:
        result = _retry(
            lambda: exchange.set_leverage(leverage, f"{coin}/USDT"),
            retries=3, base_delay=2
        )
        if result is not None:
            log.info(f"[LIVE] Leverage set: {coin} {leverage}x")
            return True
        log.error(f"[LIVE] Leverage set failed: {coin}")
        return False

    def ensure_isolated(self, coin: str):
        try:
            exchange.set_margin_mode("isolated", f"{coin}/USDT")
            log.info(f"[LIVE] Margin mode set ISOLATED: {coin}")
        except Exception as e:
            log.warning(f"Margin mode set failed {coin}: {e}")

    def _handle_partial_fill(self, coin: str, order: dict, filled: float, expected: float):
        try:
            with get_session() as db:
                db.add(AuditLog(
                    action  = "partial_fill",
                    source  = "live_executor",
                    detail  = f"{coin} filled:{filled} expected:{expected} order_id:{order.get('id')}",
                    success = True
                ))
        except Exception as e:
            log.error(f"Partial fill audit error: {e}")

    def _audit(self, action: str, coin: str, detail: str = ""):
        try:
            with get_session() as db:
                db.add(AuditLog(
                    action  = action,
                    source  = "live_executor",
                    detail  = f"{coin} {detail}",
                    success = True
                ))
        except Exception as e:
            log.error(f"Live executor audit error: {e}")


live_executor = LiveOrderExecutor()