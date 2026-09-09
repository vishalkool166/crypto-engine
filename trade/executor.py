import asyncio
import logging
import math
from datetime import datetime, timezone
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx
from config import cfg, TAKER_FEE, ORDER_FILL_TIMEOUT, ORDER_POLL_INTERVAL, MIN_STAKE_USDT, ENTRY_DEVIATION_MULT
from trade.exchange import (
    get_balance, get_positions, get_ticker_price,
    set_leverage, set_margin_mode, place_order,
    cancel_order, get_order, cancel_all_orders,
    get_open_orders, get_symbol_precision,
    get_commission_from_order, place_algo_order,
    cancel_all_algo_orders,
)
from database import get_session, Trade as TradeModel, Signal as SignalModel

log = logging.getLogger(__name__)

HE = cfg.HYBRID_ENGINE

CLOSE_REASONS = {
    "tp1_hit":                "Take profit reached",
    "tp2_hit":                "Take profit 2 reached",
    "sl_hit":                 "Stop loss triggered",
    "manual_close":           "Manual close",
    "manual_dashboard_close": "Dashboard force close",
    "exchange_closed":        "Position closed on exchange",
    "liquidated":             "Liquidation triggered",
    "deviation_rejected":     "Entry rejected — price moved too far",
}

SESSION_EXPIRY_HOURS = {
    "London/NY Overlap": 2,
    "London":            3,
    "New York":          3,
    "Off Hours":         1,
    "Asia":              1,
}

DEFAULT_EXPIRY_HOURS = HE.get("limit_order_expiry_hours", 4)


def _get_session_expiry() -> int:
    hour = datetime.now(timezone.utc).hour
    if 8  <= hour < 13:  session = "London"
    elif 13 <= hour < 17: session = "London/NY Overlap"
    elif 17 <= hour < 21: session = "New York"
    elif 0  <= hour < 8:  session = "Asia"
    else:                  session = "Off Hours"
    return SESSION_EXPIRY_HOURS.get(session, DEFAULT_EXPIRY_HOURS)


def _round_tick(price: float, tick_size: float) -> float:
    if not tick_size or tick_size <= 0:
        return price
    precision = max(0, int(round(-math.log10(tick_size)))) if tick_size < 1 else 0
    return round(math.floor(price / tick_size) * tick_size, precision)


def _round_step(quantity: float, step_size: float) -> float:
    if not step_size or step_size <= 0:
        return quantity
    precision = max(0, int(round(-math.log10(step_size)))) if step_size < 1 else 0
    return round(math.floor(quantity / step_size) * step_size, precision)


@retry(
    retry   = retry_if_exception_type(httpx.NetworkError),
    stop    = stop_after_attempt(3),
    wait    = wait_exponential(multiplier=1, min=2, max=10),
    reraise = True,
)
async def _place_with_retry(**kwargs) -> dict:
    return await place_order(**kwargs)


@retry(
    retry   = retry_if_exception_type(httpx.NetworkError),
    stop    = stop_after_attempt(3),
    wait    = wait_exponential(multiplier=1, min=2, max=10),
    reraise = True,
)
async def _fetch_order(symbol: str, order_id: str) -> dict:
    return await get_order(symbol, order_id)


async def _wait_for_fill(symbol: str, order_id: str) -> dict:
    deadline = asyncio.get_event_loop().time() + ORDER_FILL_TIMEOUT
    while asyncio.get_event_loop().time() < deadline:
        order  = await _fetch_order(symbol, order_id)
        status = order.get("status", "")
        if status == "FILLED":
            return order
        if status in ("CANCELED", "EXPIRED", "REJECTED"):
            raise RuntimeError(f"Order {order_id} status: {status}")
        await asyncio.sleep(ORDER_POLL_INTERVAL)
    await cancel_order(symbol, order_id)
    raise RuntimeError(f"Order {order_id} timeout after {ORDER_FILL_TIMEOUT}s")


async def _wait_for_limit_fill(symbol: str, order_id: str, expiry_hours: int) -> dict | None:
    expiry   = expiry_hours * 3600
    deadline = asyncio.get_event_loop().time() + expiry
    while asyncio.get_event_loop().time() < deadline:
        order  = await _fetch_order(symbol, order_id)
        status = order.get("status", "")
        if status == "FILLED":
            return order
        if status in ("CANCELED", "EXPIRED", "REJECTED"):
            return None
        await asyncio.sleep(30)
    try:
        await cancel_order(symbol, order_id)
    except Exception:
        pass
    log.info("Limit order expired after %sh: %s", expiry_hours, order_id)
    return None


async def _get_commission(symbol: str, order_id: str) -> dict:
    try:
        from trade.ws import get_pending_commission, clear_pending_commission
        cached = get_pending_commission(order_id)
        if cached:
            clear_pending_commission(order_id)
            return cached
    except Exception:
        pass
    return await get_commission_from_order(symbol, order_id)


def _calc_pnl(
    direction:    str,
    entry:        float,
    exit_price:   float,
    position_amt: float,
    commission:   float = 0.0,
) -> float:
    if not entry or not exit_price or not position_amt:
        return 0.0
    gross = position_amt * (exit_price - entry)
    return round(gross - commission, 4)


def _get_field(trade_id: int, field: str) -> float:
    try:
        with get_session() as db:
            trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            return float(getattr(trade, field, 0) or 0) if trade else 0.0
    except Exception:
        return 0.0


def _create_pending_trade(
    coin:      str,
    direction: str,
    signal_id: int | None,
    grade:     str,
    sl_price:  float,
    tp1_price: float,
    tp2_price: float | None,
    leverage:  int,
    regime:    str = "",
    session:   str = "",
    score:     float = 0.0,
) -> int:
    try:
        from datetime import date as _date
        with get_session() as db:
            trade = TradeModel(
                signal_id        = signal_id,
                coin             = coin,
                direction        = direction,
                grade            = grade,
                state            = "pending",
                is_active        = False,
                sl_price         = sl_price,
                tp1_price        = tp1_price,
                tp2_price        = tp2_price,
                leverage         = leverage,
                opened_at        = datetime.now(timezone.utc),
                outcome          = "pending",
                regime_at_entry  = regime,
                session_at_entry = session,
                score_at_entry   = score,
                trade_date       = _date.today().isoformat(),
                system_version   = cfg.SYSTEM_VERSION,
            )
            db.add(trade)
            db.flush()
            db.refresh(trade)
            log.info("Pending trade created: id:%s %s %s", trade.id, coin, direction)
            return trade.id
    except Exception as e:
        log.error("_create_pending_trade error: %s", e)
        return 0


def _activate_trade(
    trade_id:           int,
    entry_price:        float,
    position_amt:       float,
    position_size:      float,
    margin_used:        float,
    sl_order_id:        str | None,
    tp1_order_id:       str | None,
    entry_order_id:     str,
    actual_fill_entry:  float = 0.0,
    slippage_entry_pct: float = 0.0,
    entry_commission:   float = 0.0,
    entry_role:         str   = "maker",
    sizing_result:      dict  = None,
) -> None:
    try:
        with get_session() as db:
            trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if not trade:
                return
            trade.state              = "open"
            trade.is_active          = True
            trade.entry_price        = entry_price
            trade.position_size      = position_amt
            trade.margin_used        = margin_used
            trade.sl_order_id        = sl_order_id
            trade.tp1_order_id       = tp1_order_id
            trade.entry_order_id     = entry_order_id
            trade.balance_at_open    = margin_used
            trade.actual_fill_entry  = actual_fill_entry or entry_price
            trade.slippage_entry_pct = slippage_entry_pct
            trade.entry_commission   = entry_commission
            trade.entry_role         = entry_role
            trade.funding_fees_paid  = 0.0
            trade.total_commission   = entry_commission

            if sizing_result:
                trade.drawdown_at_entry    = sizing_result.get("drawdown_pct")
                trade.win_rate_at_entry    = sizing_result.get("win_rate")
                trade.streak_at_entry      = sizing_result.get("streak")
                trade.streak_type_at_entry = sizing_result.get("streak_type")
                trade.daily_pnl_at_entry   = sizing_result.get("today_pnl")
                trade.open_trades_at_entry = sizing_result.get("open_trades")

            log.info(
                "Trade activated: id:%s fill:%.6f position_amt:%.6f slip:%.4f%% fee:$%.8f",
                trade_id, actual_fill_entry, position_amt, slippage_entry_pct, entry_commission,
            )
    except Exception as e:
        log.error("_activate_trade error: %s", e)


def _mark_closed(
    trade_id:          int,
    exit_price:        float,
    pnl:               float,
    reason:            str,
    exit_commission:   float = 0.0,
    exit_role:         str   = "taker",
    total_commission:  float = 0.0,
    realized_pnl:      float = 0.0,
    slippage_exit_pct: float = 0.0,
) -> None:
    try:
        with get_session() as db:
            trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if not trade:
                return
            trade.is_active             = False
            trade.state                 = "closed"
            trade.exit_price            = exit_price
            trade.actual_fill_exit      = exit_price
            trade.slippage_exit_pct     = round(slippage_exit_pct, 4)
            trade.pnl                   = pnl
            trade.net_pnl               = pnl
            trade.close_reason          = reason
            trade.closed_at             = datetime.now(timezone.utc)
            trade.outcome               = "win" if pnl > 0 else "loss"
            trade.tp1_hit               = reason == "tp1_hit"
            trade.exit_commission       = round(exit_commission, 8)
            trade.exit_role             = exit_role
            trade.total_commission      = round(total_commission, 8)
            trade.realized_pnl_exchange = round(realized_pnl, 8)

            if trade.opened_at:
                opened = trade.opened_at
                if opened.tzinfo is None:
                    opened = opened.replace(tzinfo=timezone.utc)
                trade.duration_hours = round(
                    (datetime.now(timezone.utc) - opened).total_seconds() / 3600, 2
                )

            if trade.signal_id:
                sig = db.query(SignalModel).filter(SignalModel.id == trade.signal_id).first()
                if sig:
                    sig.outcome    = trade.outcome
                    sig.pnl        = pnl
                    sig.exit_price = exit_price

            log.info(
                "Trade closed: id:%s exit:%.6f pnl:%.4f fee:$%.8f reason:%s",
                trade_id, exit_price, pnl, total_commission, reason,
            )
    except Exception as e:
        log.error("_mark_closed error: %s", e)


def _cancel_pending_trade(trade_id: int) -> None:
    try:
        with get_session() as db:
            trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if trade and trade.state == "pending":
                trade.state   = "cancelled"
                trade.outcome = "cancelled"
                log.info("Pending trade cancelled: id:%s", trade_id)
    except Exception as e:
        log.error("_cancel_pending_trade error: %s", e)


async def open_position(
    coin:      str,
    direction: str,
    entry:     float,
    sl:        float,
    tp:        float,
    stake:     float,
    leverage:  int,
    signal_id: int | None   = None,
    grade:     str          = "",
    regime:    str          = "",
    session:   str          = "",
    score:     float        = 0.0,
    tp2:       float | None = None,
    atr_15m:   float        = 0.0,
    sizing_result: dict     = None,
) -> dict:
    symbol   = f"{coin}USDT"
    is_short = direction == "SHORT"
    side     = "SELL" if is_short else "BUY"
    sl_side  = "BUY"  if is_short else "SELL"
    tp_side  = "BUY"  if is_short else "SELL"
    trade_id = 0

    try:
        current = await get_ticker_price(symbol)
        if not current:
            return {"success": False, "error": "Could not fetch price"}

        balance = await get_balance()
        if balance["free"] < stake:
            return {"success": False, "error": f"Insufficient balance ${balance['free']:.2f}"}

        positions = await get_positions()
        existing  = next(
            (p for p in positions
             if p.get("symbol") == symbol and float(p.get("positionAmt", 0)) != 0),
            None,
        )
        if existing:
            return {"success": False, "error": f"Position already exists for {coin}"}

        trade_id = _create_pending_trade(
            coin      = coin,
            direction = direction,
            signal_id = signal_id,
            grade     = grade,
            sl_price  = sl,
            tp1_price = tp,
            tp2_price = tp2,
            leverage  = leverage,
            regime    = regime,
            session   = session,
            score     = score,
        )

        if not trade_id:
            return {"success": False, "error": "Failed to create trade record"}

        await set_margin_mode(symbol, "ISOLATED")
        await set_leverage(symbol, leverage)

        prec            = await get_symbol_precision(symbol)
        qty_step        = prec["step_size"]
        min_qty         = prec["min_qty"]
        tick_size       = prec["tick_size"]
        price_precision = prec["price_precision"]

        total_quantity = _round_step((stake * leverage) / current, qty_step)

        if min_qty > 0 and total_quantity < min_qty:
            _cancel_pending_trade(trade_id)
            return {"success": False, "error": f"Quantity {total_quantity} below minimum {min_qty}"}

        entry_rounded = _round_tick(entry, tick_size)
        sl_rounded    = _round_tick(sl,    tick_size)
        tp1_rounded   = _round_tick(tp,    tick_size)

        expiry_hours = _get_session_expiry()

        log.info(
            "Opening LIMIT: %s %s limit:%.6f qty:%s stake:%.2f lev:%dx sl:%s tp:%s expiry:%sh",
            coin, direction, entry_rounded, total_quantity,
            stake, leverage, sl_rounded, tp1_rounded, expiry_hours,
        )

        raw       = await _place_with_retry(
            symbol     = symbol,
            side       = side,
            order_type = "LIMIT",
            quantity   = total_quantity,
            price      = entry_rounded,
        )
        entry_oid = str(raw.get("orderId", ""))

        log.info(
            "Limit order placed: %s %s price:%.6f qty:%s order_id:%s expiry:%sh",
            coin, direction, entry_rounded, total_quantity, entry_oid, expiry_hours,
        )

        from alerts.telegram import send
        mode  = "DEMO" if cfg.TRADING_MODE != "live" else "LIVE"
        emoji = "📈" if direction == "LONG" else "📉"
        await send(
            f"{emoji} *{coin} {direction} Limit Order Placed — {mode}*\n\n"
            f"Limit:   `{entry_rounded}` (zone level)\n"
            f"Current: `{current:.6f}`\n"
            f"SL:      `{sl_rounded}`\n"
            f"TP:      `{tp1_rounded}`\n"
            f"Stake:   `${stake:.2f}` × `{leverage}x`\n"
            f"Grade:   `{grade}` · Score `{score}`\n"
            f"Expires: `{expiry_hours}h` ({session or 'current session'})"
        )

        asyncio.create_task(
            _monitor_limit_order(
                trade_id        = trade_id,
                coin            = coin,
                symbol          = symbol,
                direction       = direction,
                entry_oid       = entry_oid,
                entry_rounded   = entry_rounded,
                total_quantity  = total_quantity,
                qty_step        = qty_step,
                sl_rounded      = sl_rounded,
                tp1_rounded     = tp1_rounded,
                sl_side         = sl_side,
                tp_side         = tp_side,
                price_precision = price_precision,
                tick_size       = tick_size,
                stake           = stake,
                leverage        = leverage,
                grade           = grade,
                score           = score,
                sizing_result   = sizing_result,
                expiry_hours    = expiry_hours,
                session         = session or "",
                tp2             = tp2,
            )
        )

        return {
            "success":      True,
            "trade_id":     trade_id,
            "order_id":     entry_oid,
            "limit_price":  entry_rounded,
            "quantity":     total_quantity,
            "expiry_hours": expiry_hours,
            "pending":      True,
        }

    except Exception as e:
        log.error("open_position %s: %s", coin, e, exc_info=True)
        if trade_id:
            _cancel_pending_trade(trade_id)
        return {"success": False, "error": str(e)}


async def _monitor_limit_order(
    trade_id:       int,
    coin:           str,
    symbol:         str,
    direction:      str,
    entry_oid:      str,
    entry_rounded:  float,
    total_quantity: float,
    qty_step:       float,
    sl_rounded:     float,
    tp1_rounded:    float,
    sl_side:        str,
    tp_side:        str,
    price_precision:int,
    tick_size:      float,
    stake:          float,
    leverage:       int,
    grade:          str,
    score:          float,
    sizing_result:  dict,
    expiry_hours:   int,
    session:        str = "",
    tp2:            float | None = None,
) -> None:
    try:
        filled = await _wait_for_limit_fill(symbol, entry_oid, expiry_hours)

        if not filled:
            _cancel_pending_trade(trade_id)
            log.info("Limit order not filled — trade cancelled: %s %s", coin, direction)
            from alerts.telegram import send
            emoji = "📈" if direction == "LONG" else "📉"
            await send(
                f"{emoji} *{coin} {direction} Limit Expired*\n\n"
                f"Price never reached `{entry_rounded}`\n"
                f"Expired after `{expiry_hours}h` ({session or 'session'})\n"
                f"Order cancelled — no loss."
            )
            return

        fill_price    = float(filled.get("avgPrice") or filled.get("price") or entry_rounded)
        filled_qty    = _round_step(float(filled.get("executedQty", total_quantity)), qty_step)
        signed_qty    = -filled_qty if direction == "SHORT" else filled_qty
        actual_margin = round(abs(filled_qty * fill_price) / leverage, 8)

        log.info("Limit filled: %s %.6f qty:%s", coin, fill_price, filled_qty)

        await asyncio.sleep(3.0)

        comm         = await _get_commission(symbol, entry_oid)
        entry_fee    = float(comm.get("commission", 0))
        entry_role   = comm.get("role", "maker")
        slippage_pct = abs(fill_price - entry_rounded) / entry_rounded * 100 if entry_rounded > 0 else 0.0

        sl_oid = await _place_sl(symbol, sl_side, sl_rounded, price_precision, tick_size)

        if not sl_oid:
            log.error("SL placement failed for %s — closing position immediately", coin)
            try:
                close_side = "BUY" if direction == "SHORT" else "SELL"
                await _place_with_retry(
                    symbol      = symbol,
                    side        = close_side,
                    order_type  = "MARKET",
                    quantity    = total_quantity,
                    reduce_only = True,
                )
                log.info("Emergency close executed for %s", coin)
            except Exception as ce:
                log.error("Emergency close failed %s: %s", coin, ce)
            _cancel_pending_trade(trade_id)
            from alerts.telegram import send
            await send(
                f"🚨 *SL Failed — Position Closed*\n\n"
                f"`{coin}` {direction}\n"
                f"Stop loss could not be placed.\n"
                f"Position closed immediately to protect capital.\n"
                f"Entry was: `{fill_price:.6f}`"
            )
            return

        tp1_oid = await _place_tp(symbol, tp_side, tp1_rounded, price_precision, tick_size, "TP1")

        _activate_trade(
            trade_id           = trade_id,
            entry_price        = fill_price,
            position_amt       = signed_qty,
            position_size      = signed_qty,
            margin_used        = actual_margin,
            sl_order_id        = sl_oid,
            tp1_order_id       = tp1_oid,
            entry_order_id     = entry_oid,
            actual_fill_entry  = fill_price,
            slippage_entry_pct = round(slippage_pct, 4),
            entry_commission   = entry_fee,
            entry_role         = entry_role,
            sizing_result      = sizing_result,
        )

        from alerts.telegram import send
        mode      = "DEMO" if cfg.TRADING_MODE != "live" else "LIVE"
        emoji     = "📈" if direction == "LONG" else "📉"
        sl_status = "✅" if sl_oid  else "⚠️ FAILED"
        tp_status = "✅" if tp1_oid else "⚠️ Failed"

        await send(
            f"{emoji} *{coin} {direction} FILLED — {mode}*\n\n"
            f"Fill:    `{fill_price}` (limit `{entry_rounded}` slip `{slippage_pct:.4f}%`)\n"
            f"SL:      `{sl_rounded}` {sl_status}\n"
            f"TP:      `{tp1_rounded}` {tp_status}\n"
            f"Stake:   `${stake:.2f}` × `{leverage}x` = `${stake*leverage:.2f}`\n"
            f"Fee:     `${entry_fee:.8f}` ({entry_role})\n"
            f"Grade:   `{grade}` · Score `{score}`"
        )

    except Exception as e:
        log.error("_monitor_limit_order %s: %s", coin, e, exc_info=True)
        if trade_id:
            _cancel_pending_trade(trade_id)


async def _place_sl(
    symbol:          str,
    side:            str,
    sl:              float,
    price_precision: int   = 8,
    tick_size:       float = 0.0,
) -> str | None:
    if tick_size and tick_size > 0:
        sl = _round_tick(sl, tick_size)
    try:
        order    = await place_algo_order(
            symbol          = symbol,
            side            = side,
            order_type      = "STOP_MARKET",
            trigger_price   = sl,
            price_precision = price_precision,
            close_position  = True,
        )
        order_id = str(order.get("orderId", ""))
        algo_id  = str(order.get("algoId",  ""))
        ref_id   = order_id if order_id and order_id != "0" else algo_id
        if ref_id and ref_id != "0":
            log.info("SL placed: %s sl:%s orderId:%s algoId:%s", symbol, sl, order_id, algo_id)
            return ref_id
    except Exception as e:
        log.error("SL order failed %s: %s", symbol, e)
    return None


async def _place_tp(
    symbol:          str,
    side:            str,
    tp:              float,
    price_precision: int   = 8,
    tick_size:       float = 0.0,
    label:           str   = "TP",
) -> str | None:
    if tick_size and tick_size > 0:
        tp = _round_tick(tp, tick_size)
    try:
        order    = await place_algo_order(
            symbol          = symbol,
            side            = side,
            order_type      = "TAKE_PROFIT_MARKET",
            trigger_price   = tp,
            price_precision = price_precision,
            close_position  = True,
        )
        order_id = str(order.get("orderId", ""))
        algo_id  = str(order.get("algoId",  ""))
        ref_id   = order_id if order_id and order_id != "0" else algo_id
        if ref_id and ref_id != "0":
            log.info("%s placed: %s tp:%s orderId:%s algoId:%s", label, symbol, tp, order_id, algo_id)
            return ref_id
    except Exception as e:
        log.error("%s order failed %s: %s", label, symbol, e)
    return None


async def close_position(
    coin:      str,
    direction: str,
    trade_id:  int,
    reason:    str = "manual_dashboard_close",
) -> dict:
    symbol   = f"{coin}USDT"
    is_short = direction == "SHORT"

    try:
        positions = await get_positions()
        position  = next(
            (p for p in positions
             if p.get("symbol") == symbol and float(p.get("positionAmt", 0)) != 0),
            None,
        )

        if not position:
            log.warning("No open position for %s", coin)
            _mark_closed(trade_id, 0.0, 0.0, reason)
            return {"success": False, "error": "No open position found"}

        await _cleanup_orders(symbol)

        qty        = abs(float(position.get("positionAmt", 0)))
        close_side = "BUY" if is_short else "SELL"

        prec     = await get_symbol_precision(symbol)
        qty_step = prec["step_size"]
        qty      = _round_step(qty, qty_step)

        raw        = await _place_with_retry(
            symbol      = symbol,
            side        = close_side,
            order_type  = "MARKET",
            quantity    = qty,
            reduce_only = True,
        )
        filled     = await _wait_for_fill(symbol, raw["orderId"])
        close_oid  = str(filled.get("orderId", ""))
        exit_price = float(filled.get("avgPrice") or filled.get("price") or 0)

        await asyncio.sleep(2.0)
        comm         = await _get_commission(symbol, close_oid)
        exit_fee     = float(comm.get("commission",   0))
        exit_role    = comm.get("role", "taker")
        realized_pnl = float(comm.get("realized_pnl", 0))
        entry_fee    = _get_field(trade_id, "entry_commission")
        total_fee    = round(entry_fee + exit_fee, 8)

        position_amt = _get_field(trade_id, "position_size")
        entry_price  = _get_field(trade_id, "entry_price")

        net_pnl = (
            round(realized_pnl - total_fee, 8) if realized_pnl != 0
            else _calc_pnl(
                direction    = direction,
                entry        = entry_price,
                exit_price   = exit_price,
                position_amt = position_amt,
                commission   = total_fee,
            )
        )

        _mark_closed(
            trade_id         = trade_id,
            exit_price       = exit_price,
            pnl              = net_pnl,
            reason           = reason,
            exit_commission  = exit_fee,
            exit_role        = exit_role,
            total_commission = total_fee,
            realized_pnl     = realized_pnl,
        )

        try:
            from ml.outcome_recorder import record
            asyncio.create_task(record(trade_id))
        except Exception:
            pass

        from alerts.telegram import send
        emoji        = "✅" if net_pnl >= 0 else "❌"
        pnl_str      = f"+${net_pnl:.4f}" if net_pnl >= 0 else f"-${abs(net_pnl):.4f}"
        reason_label = CLOSE_REASONS.get(reason, reason)
        await send(
            f"{emoji} *{coin} {direction} Closed*\n\n"
            f"Exit:     `{exit_price}`\n"
            f"PnL:      `{pnl_str}`\n"
            f"Fee:      `${total_fee:.8f}` ({exit_role})\n"
            f"Reason:   `{reason_label}`\n"
        )

        return {"success": True, "exit_price": exit_price, "pnl": net_pnl}

    except Exception as e:
        log.error("close_position %s: %s", coin, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def _cleanup_orders(symbol: str) -> None:
    try:
        await cancel_all_orders(symbol)
        await cancel_all_algo_orders(symbol)
        await asyncio.sleep(1.0)
        for order in await get_open_orders(symbol):
            oid = str(order.get("orderId", ""))
            if oid:
                await cancel_order(symbol, oid)
    except Exception as e:
        log.warning("_cleanup_orders %s: %s", symbol, e)


def has_open_trade(coin: str) -> bool:
    try:
        with get_session() as db:
            return db.query(TradeModel).filter(
                TradeModel.coin      == coin,
                TradeModel.is_active == True,
            ).first() is not None
    except Exception:
        return False


async def has_open_trade_or_position(coin: str) -> bool:
    if has_open_trade(coin):
        return True
    try:
        symbol    = f"{coin}USDT"
        positions = await get_positions()
        return any(
            p.get("symbol") == symbol and float(p.get("positionAmt", 0)) != 0
            for p in positions
        )
    except Exception:
        return False


def get_open_trade_count() -> int:
    try:
        with get_session() as db:
            return db.query(TradeModel).filter(TradeModel.is_active == True).count()
    except Exception:
        return 0