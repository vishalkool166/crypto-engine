import logging
import time
from datetime import datetime, timezone
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import ccxt
from trade.exchange import get_exchange, get_balance
from database import get_session, Trade as TradeModel, Signal as SignalModel
from config import cfg

log = logging.getLogger(__name__)

MAX_ENTRY_DEVIATION_PCT = 0.20
MIN_STAKE               = 5.0
ORDER_FILL_TIMEOUT_SECS = 60
ORDER_POLL_INTERVAL     = 3


class EntryDeviationError(Exception):
    pass


class InsufficientBalanceError(Exception):
    pass


class OrderFailedError(Exception):
    pass


def _deviation_check(
    signal_entry: float,
    current_price: float,
    sl:           float,
    direction:    str
) -> tuple[bool, str]:
    if not signal_entry or not current_price or not sl:
        return False, "Missing price data"

    sl_distance    = abs(signal_entry - sl) / signal_entry
    max_adverse    = sl_distance * 0.20
    max_favorable  = sl_distance * 0.50

    if direction == "SHORT":
        deviation = (current_price - signal_entry) / signal_entry
        if deviation > max_adverse:
            return False, (
                f"Price moved {deviation*100:.2f}% adverse for SHORT "
                f"(max {max_adverse*100:.2f}%)"
            )
        if deviation < -max_favorable:
            log.info(
                f"Price moved {abs(deviation)*100:.2f}% favorable for SHORT — allowing"
            )
    else:
        deviation = (signal_entry - current_price) / signal_entry
        if deviation > max_adverse:
            return False, (
                f"Price moved {deviation*100:.2f}% adverse for LONG "
                f"(max {max_adverse*100:.2f}%)"
            )
        if deviation < -max_favorable:
            log.info(
                f"Price moved {abs(deviation)*100:.2f}% favorable for LONG — allowing"
            )

    return True, ""


@retry(
    retry     = retry_if_exception_type(ccxt.NetworkError),
    stop      = stop_after_attempt(3),
    wait      = wait_exponential(multiplier=1, min=2, max=10),
    reraise   = True
)
async def _place_order(
    exchange,
    symbol:     str,
    order_type: str,
    side:       str,
    amount:     float,
    price:      float = None,
    params:     dict  = None
) -> dict:
    return await exchange.create_order(
        symbol     = symbol,
        type       = order_type,
        side       = side,
        amount     = amount,
        price      = price,
        params     = params or {}
    )


@retry(
    retry   = retry_if_exception_type(ccxt.NetworkError),
    stop    = stop_after_attempt(3),
    wait    = wait_exponential(multiplier=1, min=2, max=10),
    reraise = True
)
async def _fetch_order(exchange, order_id: str, symbol: str) -> dict:
    return await exchange.fetch_order(order_id, symbol)


@retry(
    retry   = retry_if_exception_type(ccxt.NetworkError),
    stop    = stop_after_attempt(3),
    wait    = wait_exponential(multiplier=1, min=2, max=10),
    reraise = True
)
async def _cancel_order(exchange, order_id: str, symbol: str) -> dict:
    return await exchange.cancel_order(order_id, symbol)


async def _wait_for_fill(
    exchange,
    order_id: str,
    symbol:   str,
    timeout:  int = ORDER_FILL_TIMEOUT_SECS
) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        order = await _fetch_order(exchange, order_id, symbol)
        status = order.get("status", "")

        if status == "closed":
            return order
        if status == "canceled":
            raise OrderFailedError(f"Order {order_id} was canceled")
        if status == "rejected":
            raise OrderFailedError(f"Order {order_id} was rejected")

        await __import__("asyncio").sleep(ORDER_POLL_INTERVAL)

    await _cancel_order(exchange, order_id, symbol)
    raise OrderFailedError(
        f"Order {order_id} not filled within {timeout}s — canceled"
    )


def _get_amount_precision(exchange, symbol: str) -> int:
    try:
        market = exchange.market(symbol)
        return int(market.get("precision", {}).get("amount", 1))
    except Exception:
        return 1


def _round_amount(amount: float, precision: int) -> float:
    factor = 10 ** precision
    return int(amount * factor) / factor


async def open_position(
    coin:      str,
    direction: str,
    entry:     float,
    sl:        float,
    tp:        float,
    stake:     float,
    leverage:  int,
    signal_id: int  = None,
    grade:     str  = "",
) -> dict:
    exchange = get_exchange()
    symbol   = f"{coin}/USDT:USDT"
    is_short = direction == "SHORT"
    side     = "sell" if is_short else "buy"

    try:
        await exchange.load_markets()

        current_price = await __import__(
            "trade.exchange", fromlist=["get_ticker_price"]
        ).__class__
        from trade.exchange import get_ticker_price
        current_price = await get_ticker_price(symbol)

        if not current_price:
            return {"success": False, "error": "Could not fetch current price"}

        ok, reason = _deviation_check(entry, current_price, sl, direction)
        if not ok:
            log.warning(f"Entry deviation check failed: {coin} {direction} — {reason}")
            return {"success": False, "error": reason, "deviation_rejected": True}

        balance = await get_balance()
        if balance["free"] < stake:
            return {
                "success": False,
                "error":   f"Insufficient balance: ${balance['free']:.2f} < ${stake:.2f}"
            }

        await exchange.set_leverage(leverage, symbol)
        await exchange.set_margin_mode("isolated", symbol)

        precision = _get_amount_precision(exchange, symbol)
        amount    = _round_amount((stake * leverage) / current_price, precision)

        if amount <= 0:
            return {"success": False, "error": f"Calculated amount is zero for {coin}"}

        log.info(
            f"Opening position: {coin} {direction} "
            f"price:{current_price} amount:{amount} "
            f"stake:{stake:.2f} leverage:{leverage}x "
            f"sl:{sl} tp:{tp}"
        )

        entry_order = await _place_order(
            exchange   = exchange,
            symbol     = symbol,
            order_type = "market",
            side       = side,
            amount     = amount,
        )

        entry_order = await _wait_for_fill(
            exchange = exchange,
            order_id = entry_order["id"],
            symbol   = symbol,
        )

        fill_price = float(entry_order.get("average") or entry_order.get("price") or current_price)
        filled_amt = float(entry_order.get("filled", amount))

        log.info(f"Entry filled: {coin} {direction} fill_price:{fill_price} amount:{filled_amt}")

        sl_order_id = None
        tp_order_id = None

        try:
            sl_side   = "buy" if is_short else "sell"
            sl_params = {
                "stopPrice":   sl,
                "reduceOnly":  True,
                "workingType": "MARK_PRICE",
            }
            sl_order = await _place_order(
                exchange   = exchange,
                symbol     = symbol,
                order_type = "stop_market",
                side       = sl_side,
                amount     = filled_amt,
                params     = sl_params,
            )
            sl_order_id = sl_order.get("id")
            log.info(f"SL order placed: {coin} sl:{sl} order_id:{sl_order_id}")
        except Exception as e:
            log.error(f"SL order failed {coin}: {e}")

        try:
            tp_side   = "buy" if is_short else "sell"
            tp_params = {
                "reduceOnly": True,
            }
            tp_order = await _place_order(
                exchange   = exchange,
                symbol     = symbol,
                order_type = "limit",
                side       = tp_side,
                amount     = filled_amt,
                price      = tp,
                params     = tp_params,
            )
            tp_order_id = tp_order.get("id")
            log.info(f"TP order placed: {coin} tp:{tp} order_id:{tp_order_id}")
        except Exception as e:
            log.error(f"TP order failed {coin}: {e}")

        trade_id = _save_trade(
            coin         = coin,
            direction    = direction,
            signal_id    = signal_id,
            grade        = grade,
            entry_price  = fill_price,
            sl_price     = sl,
            tp1_price    = tp,
            position_size= stake * leverage,
            margin_used  = stake,
            leverage     = leverage,
            sl_order_id  = sl_order_id,
            tp1_order_id = tp_order_id,
            entry_order_id = entry_order["id"],
        )

        from alerts.telegram import send
        mode  = "DEMO" if cfg.TRADING_MODE != "live" else "LIVE"
        emoji = "📈" if direction == "LONG" else "📉"
        await send(
            f"{emoji} *{coin} {direction} Opened — {mode}*\n\n"
            f"Entry:    `${fill_price:.6f}`\n"
            f"SL:       `${sl:.6f}`\n"
            f"TP:       `${tp:.6f}`\n"
            f"Stake:    `${stake:.2f}` × `{leverage}x`\n"
            f"Position: `${stake * leverage:.2f}`\n"
            f"Grade:    `{grade}`"
        )

        return {
            "success":    True,
            "trade_id":   trade_id,
            "fill_price": fill_price,
            "amount":     filled_amt,
            "sl_order":   sl_order_id,
            "tp_order":   tp_order_id,
        }

    except EntryDeviationError as e:
        return {"success": False, "error": str(e), "deviation_rejected": True}
    except InsufficientBalanceError as e:
        return {"success": False, "error": str(e)}
    except OrderFailedError as e:
        log.error(f"Order failed {coin}: {e}")
        return {"success": False, "error": str(e)}
    except ccxt.InsufficientFunds as e:
        log.error(f"Insufficient funds {coin}: {e}")
        return {"success": False, "error": f"Insufficient funds: {e}"}
    except ccxt.InvalidOrder as e:
        log.error(f"Invalid order {coin}: {e}")
        return {"success": False, "error": f"Invalid order: {e}"}
    except ccxt.NetworkError as e:
        log.error(f"Network error {coin}: {e}")
        return {"success": False, "error": f"Network error after retries: {e}"}
    except Exception as e:
        log.error(f"open_position error {coin}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def close_position(
    coin:         str,
    direction:    str,
    trade_id:     int,
    reason:       str = "manual",
) -> dict:
    exchange = get_exchange()
    symbol   = f"{coin}/USDT:USDT"
    is_short = direction == "SHORT"

    try:
        positions = await exchange.fetch_positions([symbol])
        position  = next(
            (p for p in positions if float(p.get("contracts", 0)) > 0),
            None
        )

        if not position:
            log.warning(f"No open position found for {coin}")
            _mark_trade_closed(trade_id, 0.0, 0.0, reason)
            return {"success": False, "error": "No open position found"}

        amount    = float(position.get("contracts", 0))
        close_side = "buy" if is_short else "sell"

        await _cancel_open_orders(exchange, symbol, trade_id)

        close_order = await _place_order(
            exchange   = exchange,
            symbol     = symbol,
            order_type = "market",
            side       = close_side,
            amount     = amount,
            params     = {"reduceOnly": True}
        )

        close_order = await _wait_for_fill(
            exchange = exchange,
            order_id = close_order["id"],
            symbol   = symbol,
        )

        exit_price = float(
            close_order.get("average") or
            close_order.get("price") or 0
        )

        pnl = _calculate_pnl(
            direction  = direction,
            entry      = _get_trade_entry(trade_id),
            exit_price = exit_price,
            position   = amount * exit_price / (
                _get_trade_leverage(trade_id) or 1
            ),
            leverage   = _get_trade_leverage(trade_id) or 1,
        )

        _mark_trade_closed(trade_id, exit_price, pnl, reason)

        from alerts.telegram import send
        emoji   = "✅" if pnl >= 0 else "❌"
        pnl_str = f"+${pnl:.4f}" if pnl >= 0 else f"-${abs(pnl):.4f}"
        await send(
            f"{emoji} *{coin} {direction} Closed*\n\n"
            f"Exit:   `${exit_price:.6f}`\n"
            f"PnL:    `{pnl_str}`\n"
            f"Reason: `{reason}`"
        )

        return {
            "success":    True,
            "exit_price": exit_price,
            "pnl":        pnl,
        }

    except OrderFailedError as e:
        log.error(f"Close order failed {coin}: {e}")
        return {"success": False, "error": str(e)}
    except ccxt.NetworkError as e:
        log.error(f"Network error closing {coin}: {e}")
        return {"success": False, "error": f"Network error: {e}"}
    except Exception as e:
        log.error(f"close_position error {coin}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def _cancel_open_orders(exchange, symbol: str, trade_id: int):
    try:
        with get_session() as db:
            trade = db.query(TradeModel).filter(
                TradeModel.id == trade_id
            ).first()
            if not trade:
                return

            for order_id in [trade.sl_order_id, trade.tp1_order_id]:
                if not order_id:
                    continue
                try:
                    await _cancel_order(exchange, order_id, symbol)
                    log.info(f"Canceled order {order_id} for {symbol}")
                except ccxt.OrderNotFound:
                    log.debug(f"Order {order_id} already gone")
                except Exception as e:
                    log.warning(f"Cancel order error {order_id}: {e}")
    except Exception as e:
        log.error(f"_cancel_open_orders error: {e}")


def _calculate_pnl(
    direction:  str,
    entry:      float,
    exit_price: float,
    position:   float,
    leverage:   int,
) -> float:
    if not entry or not exit_price or not position:
        return 0.0
    TAKER_FEE = 0.0005
    if direction == "LONG":
        gross = (exit_price - entry) / entry * position * leverage
    else:
        gross = (entry - exit_price) / entry * position * leverage
    fees = position * TAKER_FEE * 2
    return round(gross - fees, 4)


def _save_trade(
    coin:          str,
    direction:     str,
    signal_id:     int,
    grade:         str,
    entry_price:   float,
    sl_price:      float,
    tp1_price:     float,
    position_size: float,
    margin_used:   float,
    leverage:      int,
    sl_order_id:   str,
    tp1_order_id:  str,
    entry_order_id: str,
) -> int:
    try:
        with get_session() as db:
            trade = TradeModel(
                signal_id      = signal_id,
                coin           = coin,
                direction      = direction,
                grade          = grade,
                state          = "open",
                is_active      = True,
                entry_price    = entry_price,
                sl_price       = sl_price,
                tp1_price      = tp1_price,
                position_size  = position_size,
                margin_used    = margin_used,
                leverage       = leverage,
                sl_order_id    = sl_order_id,
                tp1_order_id   = tp1_order_id,
                entry_order_id = entry_order_id,
                opened_at      = datetime.now(timezone.utc),
                outcome        = "pending",
                balance_at_open= margin_used,
            )
            db.add(trade)
            db.flush()
            db.refresh(trade)
            log.info(f"Trade saved: id:{trade.id} {coin} {direction}")
            return trade.id
    except Exception as e:
        log.error(f"_save_trade error: {e}")
        return 0


def _mark_trade_closed(
    trade_id:   int,
    exit_price: float,
    pnl:        float,
    reason:     str,
):
    try:
        with get_session() as db:
            trade = db.query(TradeModel).filter(
                TradeModel.id == trade_id
            ).first()
            if not trade:
                return
            trade.is_active   = False
            trade.state       = "closed"
            trade.exit_price  = exit_price
            trade.pnl         = pnl
            trade.close_reason= reason
            trade.closed_at   = datetime.now(timezone.utc)
            trade.outcome     = "win" if pnl > 0 else "loss"

            if trade.signal_id:
                sig = db.query(SignalModel).filter(
                    SignalModel.id == trade.signal_id
                ).first()
                if sig:
                    sig.outcome    = trade.outcome
                    sig.pnl        = pnl
                    sig.exit_price = exit_price

            log.info(
                f"Trade closed: id:{trade_id} "
                f"exit:{exit_price} pnl:{pnl} reason:{reason}"
            )
    except Exception as e:
        log.error(f"_mark_trade_closed error: {e}")


def _get_trade_entry(trade_id: int) -> float:
    try:
        with get_session() as db:
            trade = db.query(TradeModel).filter(
                TradeModel.id == trade_id
            ).first()
            return float(trade.entry_price) if trade else 0.0
    except Exception:
        return 0.0


def _get_trade_leverage(trade_id: int) -> int:
    try:
        with get_session() as db:
            trade = db.query(TradeModel).filter(
                TradeModel.id == trade_id
            ).first()
            return int(trade.leverage) if trade else 1
    except Exception:
        return 1


def has_open_trade(coin: str) -> bool:
    try:
        with get_session() as db:
            trade = db.query(TradeModel).filter(
                TradeModel.coin      == coin,
                TradeModel.is_active == True,
            ).first()
            return trade is not None
    except Exception:
        return False


def get_open_trade_count() -> int:
    try:
        with get_session() as db:
            return db.query(TradeModel).filter(
                TradeModel.is_active == True
            ).count()
    except Exception:
        return 0