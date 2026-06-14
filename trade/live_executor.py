import logging
import ccxt
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import cfg
from database import get_session, AuditLog

log = logging.getLogger(__name__)

exchange = ccxt.binance({
    "apiKey": cfg.BINANCE_API_KEY,
    "secret": cfg.BINANCE_SECRET,
    "options": {"defaultType": "future"}
})

_retry_policy = dict(
    stop            = stop_after_attempt(3),
    wait            = wait_exponential(multiplier=2, min=2, max=16),
    retry           = retry_if_exception_type(ccxt.NetworkError),
    reraise         = True
)


class LiveOrderExecutor:

    @retry(**_retry_policy)
    def place_market(self, coin: str, direction: str, quantity: float) -> dict:
        try:
            side   = "buy" if direction == "LONG" else "sell"
            result = exchange.create_order(
                f"{coin}/USDT", "market", side, quantity,
                params={"reduceOnly": False}
            )
            filled = float(result.get("filled", 0))
            amount = float(result.get("amount", quantity))
            if filled < amount:
                log.warning(f"[LIVE] Partial fill: {coin} filled:{filled} expected:{amount}")
                self._handle_partial_fill(coin, result, filled, amount)

            log.info(f"[LIVE] Market order filled: {coin} {side} qty:{filled} @ {result.get('average')}")
            self._audit(f"market_{side}", coin, f"qty:{filled} avg:{result.get('average')}")
            return result
        except ccxt.ExchangeError as e:
            log.error(f"[LIVE] Market order exchange error: {coin} {e}")
            return None

    @retry(**_retry_policy)
    def place_sl(self, coin: str, direction: str, quantity: float, sl_price: float) -> dict:
        try:
            side   = "sell" if direction == "LONG" else "buy"
            result = exchange.create_order(
                f"{coin}/USDT", "stop_market", side, quantity,
                params={"stopPrice": sl_price, "reduceOnly": True, "closePosition": False}
            )
            log.info(f"[LIVE] SL placed: {coin} @ {sl_price} id:{result.get('id')}")
            self._audit("place_sl", coin, f"sl:{sl_price} qty:{quantity}")
            return result
        except ccxt.ExchangeError as e:
            log.error(f"[LIVE] SL order exchange error: {coin} {e}")
            return None

    @retry(**_retry_policy)
    def place_tp(self, coin: str, direction: str, quantity: float,
                 tp_price: float, label: str = "TP") -> dict:
        try:
            side   = "sell" if direction == "LONG" else "buy"
            result = exchange.create_order(
                f"{coin}/USDT", "take_profit_market", side, quantity,
                params={"stopPrice": tp_price, "reduceOnly": True, "closePosition": False}
            )
            log.info(f"[LIVE] {label} placed: {coin} @ {tp_price} id:{result.get('id')}")
            self._audit(f"place_{label.lower()}", coin, f"tp:{tp_price} qty:{quantity}")
            return result
        except ccxt.ExchangeError as e:
            log.error(f"[LIVE] {label} order exchange error: {coin} {e}")
            return None

    @retry(**_retry_policy)
    def cancel(self, coin: str, order_id: str) -> bool:
        try:
            exchange.cancel_order(order_id, f"{coin}/USDT")
            log.info(f"[LIVE] Order cancelled: {coin} {order_id}")
            return True
        except ccxt.ExchangeError as e:
            log.error(f"[LIVE] Cancel exchange error: {coin} {order_id} {e}")
            return False

    @retry(**_retry_policy)
    def get_status(self, coin: str, order_id: str) -> dict:
        try:
            result = exchange.fetch_order(order_id, f"{coin}/USDT")
            return {
                "id":     result.get("id"),
                "status": result.get("status"),
                "filled": float(result.get("filled", 0)),
                "amount": float(result.get("amount", 0)),
                "price":  float(result.get("average") or result.get("price") or 0)
            }
        except ccxt.ExchangeError as e:
            log.error(f"[LIVE] Get status exchange error: {coin} {order_id} {e}")
            return None

    @retry(**_retry_policy)
    def set_leverage(self, coin: str, leverage: int) -> bool:
        try:
            exchange.set_leverage(leverage, f"{coin}/USDT")
            log.info(f"[LIVE] Leverage set: {coin} {leverage}x")
            return True
        except ccxt.ExchangeError as e:
            log.error(f"[LIVE] Leverage set exchange error: {coin} {e}")
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