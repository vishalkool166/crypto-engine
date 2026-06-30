import logging
import time
import math
from datetime import datetime, timezone
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx
from trade.exchange import (
    get_balance, get_positions, get_ticker_price,
    set_leverage, set_margin_mode, place_order,
    cancel_order, get_order, cancel_all_orders,
    get_symbol_precision
)
from database import get_session, Trade as TradeModel, Signal as SignalModel
from config import cfg

log = logging.getLogger(__name__)

MIN_STAKE               = 5.0
ORDER_FILL_TIMEOUT_SECS = 60
ORDER_POLL_INTERVAL     = 3


def _round_step(quantity: float, step_size: float) -> float:
    if step_size <= 0:
        return quantity
    precision = int(round(-math.log10(step_size)))
    return round(math.floor(quantity / step_size) * step_size, precision)


def _deviation_check(
    signal_entry:  float,
    current_price: float,
    sl:            float,
    direction:     str
) -> tuple[bool, str]:
    if not signal_entry or not current_price or not sl:
        return False, "Missing price data"

    sl_distance   = abs(signal_entry - sl) / signal_entry
    max_adverse   = sl_distance * 0.35
    max_favorable = sl_distance * 0.60

    if direction == "SHORT":
        deviation = (current_price - signal_entry) / signal_entry
        if deviation > max_adverse:
            return False, (
                f"Price moved {deviation*100:.2f}% adverse for SHORT "
                f"(max {max_adverse*100:.2f}%)"
            )
    else:
        deviation = (signal_entry - current_price) / signal_entry
        if deviation > max_adverse:
            return False, (
                f"Price moved {deviation*100:.2f}% adverse for LONG "
                f"(max {max_adverse*100:.2f}%)"
            )

    return True, ""


@retry(
    retry   = retry_if_exception_type(httpx.NetworkError),
    stop    = stop_after_attempt(3),
    wait    = wait_exponential(multiplier=1, min=2, max=10),
    reraise = True
)
async def _place_order_with_retry(**kwargs) -> dict:
    return await place_order(**kwargs)


@retry(
    retry   = retry_if_exception_type(httpx.NetworkError),
    stop    = stop_after_attempt(3),
    wait    = wait_exponential(multiplier=1, min=2, max=10),
    reraise = True
)
async def _get_order_with_retry(symbol: str, order_id: str) -> dict:
    return await get_order(symbol, order_id)


@retry(
    retry   = retry_if_exception_type(httpx.NetworkError),
    stop    = stop_after_attempt(3),
    wait    = wait_exponential(multiplier=1, min=2, max=10),
    reraise = True
)
async def _cancel_order_with_retry(symbol: str, order_id: str) -> dict:
    return await cancel_order(symbol, order_id)


async def _wait_for_fill(
    symbol:   str,
    order_id: str,
    timeout:  int = ORDER_FILL_TIMEOUT_SECS
) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        order  = await _get_order_with_retry(symbol, order_id)
        status = order.get("status", "")

        if status == "FILLED":
            return order
        if status in ("CANCELED", "EXPIRED", "REJECTED"):
            raise Exception(f"Order {order_id} ended with status: {status}")

        await __import__("asyncio").sleep(ORDER_POLL_INTERVAL)

    await _cancel_order_with_retry(symbol, order_id)
    raise Exception(f"Order {order_id} not filled within {timeout}s — canceled")


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
    symbol   = f"{coin}USDT"
    is_short = direction == "SHORT"
    side     = "SELL" if is_short else "BUY"
    sl_side  = "BUY"  if is_short else "SELL"
    tp_side  = "BUY"  if is_short else "SELL"

    try:
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

        await set_margin_mode(symbol, "ISOLATED")
        await set_leverage(symbol, leverage)

        precision = await get_symbol_precision(symbol)
        qty_step  = precision.get("step_size", 0.001)
        min_qty   = precision.get("min_qty",   0.001)
        quantity  = _round_step((stake * leverage) / current_price, qty_step)

        if quantity < min_qty:
            return {
                "success": False,
                "error":   f"Quantity {quantity} below minimum {min_qty} for {coin}"
            }

        log.info(
            f"Opening position: {coin} {direction} "
            f"price:{current_price} qty:{quantity} "
            f"stake:{stake:.2f} leverage:{leverage}x "
            f"sl:{sl} tp:{tp}"
        )

        entry_order = await _place_order_with_retry(
            symbol     = symbol,
            side       = side,
            order_type = "MARKET",
            quantity   = quantity,
        )

        entry_order = await _wait_for_fill(symbol, entry_order["orderId"])

        fill_price  = float(entry_order.get("avgPrice") or entry_order.get("price") or current_price)
        filled_qty  = float(entry_order.get("executedQty", quantity))

        log.info(f"Entry filled: {coin} {direction} fill_price:{fill_price} qty:{filled_qty}")

        sl_order_id = None
        tp_order_id = None

        try:
            sl_order = await _place_order_with_retry(
                symbol      = symbol,
                side        = sl_side,
                order_type  = "STOP_MARKET",
                quantity    = filled_qty,
                stop_price  = sl,
                reduce_only = True,
                working_type= "MARK_PRICE",
            )
            sl_order_id = str(sl_order.get("orderId", ""))
            log.info(f"SL order placed: {coin} sl:{sl} order_id:{sl_order_id}")
        except Exception as e:
            log.error(f"SL order failed {coin}: {e}")

        try:
            tp_order = await _place_order_with_retry(
                symbol      = symbol,
                side        = tp_side,
                order_type  = "LIMIT",
                quantity    = filled_qty,
                price       = tp,
                reduce_only = True,
            )
            tp_order_id = str(tp_order.get("orderId", ""))
            log.info(f"TP order placed: {coin} tp:{tp} order_id:{tp_order_id}")
        except Exception as e:
            log.error(f"TP order failed {coin}: {e}")

        trade_id = _save_trade(
            coin           = coin,
            direction      = direction,
            signal_id      = signal_id,
            grade          = grade,
            entry_price    = fill_price,
            sl_price       = sl,
            tp1_price      = tp,
            position_size  = stake * leverage,
            margin_used    = stake,
            leverage       = leverage,
            sl_order_id    = sl_order_id,
            tp1_order_id   = tp_order_id,
            entry_order_id = str(entry_order.get("orderId", "")),
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
            "quantity":   filled_qty,
            "sl_order":   sl_order_id,
            "tp_order":   tp_order_id,
        }

    except Exception as e:
        log.error(f"open_position error {coin}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def close_position(
    coin:      str,
    direction: str,
    trade_id:  int,
    reason:    str = "manual",
) -> dict:
    symbol   = f"{coin}USDT"
    is_short = direction == "SHORT"

    try:
        positions = await get_positions()
        position  = next(
            (
                p for p in positions
                if p.get("symbol") == symbol and
                float(p.get("positionAmt", 0)) != 0
            ),
            None
        )

        if not position:
            log.warning(f"No open position found for {coin}")
            _mark_trade_closed(trade_id, 0.0, 0.0, reason)
            return {"success": False, "error": "No open position found"}

        await cancel_all_orders(symbol)

        quantity   = abs(float(position.get("positionAmt", 0)))
        close_side = "BUY" if is_short else "SELL"

        close_order = await _place_order_with_retry(
            symbol      = symbol,
            side        = close_side,
            order_type  = "MARKET",
            quantity    = quantity,
            reduce_only = True,
        )

        close_order = await _wait_for_fill(symbol, close_order["orderId"])

        exit_price = float(
            close_order.get("avgPrice") or
            close_order.get("price") or 0
        )

        entry    = _get_trade_entry(trade_id)
        lev      = _get_trade_leverage(trade_id)
        margin   = _get_trade_margin(trade_id)

        pnl = _calculate_pnl(
            direction  = direction,
            entry      = entry,
            exit_price = exit_price,
            margin     = margin,
            leverage   = lev,
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

    except Exception as e:
        log.error(f"close_position error {coin}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def _calculate_pnl(
    direction:  str,
    entry:      float,
    exit_price: float,
    margin:     float,
    leverage:   int,
) -> float:
    if not entry or not exit_price or not margin:
        return 0.0
    TAKER_FEE = 0.0005
    position  = margin * leverage
    if direction == "LONG":
        gross = (exit_price - entry) / entry * position
    else:
        gross = (entry - exit_price) / entry * position
    fees = position * TAKER_FEE * 2
    return round(gross - fees, 4)


def _save_trade(
    coin:           str,
    direction:      str,
    signal_id:      int,
    grade:          str,
    entry_price:    float,
    sl_price:       float,
    tp1_price:      float,
    position_size:  float,
    margin_used:    float,
    leverage:       int,
    sl_order_id:    str,
    tp1_order_id:   str,
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
            trade.is_active    = False
            trade.state        = "closed"
            trade.exit_price   = exit_price
            trade.pnl          = pnl
            trade.close_reason = reason
            trade.closed_at    = datetime.now(timezone.utc)
            trade.outcome      = "win" if pnl > 0 else "loss"

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


def _get_trade_margin(trade_id: int) -> float:
    try:
        with get_session() as db:
            trade = db.query(TradeModel).filter(
                TradeModel.id == trade_id
            ).first()
            return float(trade.margin_used) if trade else 0.0
    except Exception:
        return 0.0


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