import asyncio
import logging
import math
from datetime import datetime, timezone
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx
from config import cfg, TAKER_FEE, ORDER_FILL_TIMEOUT, ORDER_POLL_INTERVAL, MIN_STAKE_USDT, ENTRY_DEVIATION_MULT, ENTRY_FAVORABLE_MULT
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


def _round_step(quantity: float, step_size: float) -> float:
    if step_size <= 0:
        return quantity
    precision = int(round(-math.log10(step_size)))
    return round(math.floor(quantity / step_size) * step_size, precision)


def _deviation_check(
    signal_entry:  float,
    current_price: float,
    sl:            float,
    direction:     str,
) -> tuple[bool, str]:
    if not signal_entry or not current_price or not sl:
        return False, "Missing price data"
    sl_distance = abs(signal_entry - sl) / signal_entry
    max_adverse = sl_distance * ENTRY_DEVIATION_MULT
    deviation   = (
        (current_price - signal_entry) / signal_entry if direction == "SHORT"
        else (signal_entry - current_price) / signal_entry
    )
    if deviation > max_adverse:
        return False, (
            f"Price moved {deviation*100:.2f}% adverse for {direction} "
            f"(max {max_adverse*100:.2f}%)"
        )
    return True, ""


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


async def _place_sl(
    symbol:          str,
    side:            str,
    sl:              float,
    price_precision: int = 2,
) -> str | None:
    try:
        order   = await place_algo_order(
            symbol          = symbol,
            side            = side,
            order_type      = "STOP_MARKET",
            trigger_price   = sl,
            price_precision = price_precision,
            close_position  = True,
        )
        algo_id = str(order.get("algoId", ""))
        log.info("SL placed: %s sl:%s algoId:%s", symbol, round(sl, price_precision), algo_id)
        return algo_id
    except Exception as e:
        log.error("SL failed %s: %s", symbol, e)
        from alerts.telegram import send
        coin = symbol.replace("USDT", "")
        await send(
            f"⚠️ *SL Order Failed — {coin}*\n\n"
            f"Could not place SL at `${round(sl, price_precision)}`\n"
            f"Position is unprotected — place SL manually."
        )
        return None


async def _place_tp(
    symbol:          str,
    side:            str,
    tp:              float,
    price_precision: int = 2,
) -> str | None:
    try:
        order   = await place_algo_order(
            symbol          = symbol,
            side            = side,
            order_type      = "TAKE_PROFIT_MARKET",
            trigger_price   = tp,
            price_precision = price_precision,
            close_position  = True,
        )
        algo_id = str(order.get("algoId", ""))
        log.info("TP placed: %s tp:%s algoId:%s", symbol, round(tp, price_precision), algo_id)
        return algo_id
    except Exception as e:
        log.error("TP failed %s: %s", symbol, e)
        return None


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


def _calc_pnl(
    direction:  str,
    entry:      float,
    exit_price: float,
    margin:     float,
    leverage:   int,
    commission: float = 0.0,
) -> float:
    if not entry or not exit_price or not margin:
        return 0.0
    position = margin * leverage
    gross    = (
        (exit_price - entry) / entry * position if direction == "LONG"
        else (entry - exit_price) / entry * position
    )
    return round(gross - commission, 4)


def _get_field(trade_id: int, field: str) -> float:
    try:
        with get_session() as db:
            trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            return float(getattr(trade, field, 0) or 0) if trade else 0.0
    except Exception:
        return 0.0


def _save_trade(
    coin:               str,
    direction:          str,
    signal_id:          int | None,
    grade:              str,
    entry_price:        float,
    sl_price:           float,
    tp1_price:          float,
    position_size:      float,
    margin_used:        float,
    leverage:           int,
    sl_order_id:        str | None,
    tp1_order_id:       str | None,
    entry_order_id:     str,
    regime:             str   = "",
    session:            str   = "",
    score:              float = 0.0,
    actual_fill_entry:  float = 0.0,
    slippage_entry_pct: float = 0.0,
    entry_commission:   float = 0.0,
    entry_role:         str   = "taker",
) -> int:
    try:
        with get_session() as db:
            trade = TradeModel(
                signal_id          = signal_id,
                coin               = coin,
                direction          = direction,
                grade              = grade,
                state              = "open",
                is_active          = True,
                entry_price        = entry_price,
                sl_price           = sl_price,
                tp1_price          = tp1_price,
                position_size      = position_size,
                margin_used        = margin_used,
                leverage           = leverage,
                sl_order_id        = sl_order_id,
                tp1_order_id       = tp1_order_id,
                entry_order_id     = entry_order_id,
                opened_at          = datetime.now(timezone.utc),
                outcome            = "pending",
                balance_at_open    = margin_used,
                regime_at_entry    = regime,
                session_at_entry   = session,
                score_at_entry     = score,
                actual_fill_entry  = actual_fill_entry or entry_price,
                slippage_entry_pct = slippage_entry_pct,
                entry_commission   = entry_commission,
                entry_role         = entry_role,
                funding_fees_paid  = 0.0,
                total_commission   = entry_commission,
            )
            db.add(trade)
            db.flush()
            db.refresh(trade)
            log.info(
                "Trade saved: id:%s %s %s fill:%.6f slip:%.3f%% fee:$%.6f role:%s",
                trade.id, coin, direction, actual_fill_entry,
                slippage_entry_pct, entry_commission, entry_role,
            )
            return trade.id
    except Exception as e:
        log.error("_save_trade error: %s", e)
        return 0


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
            trade.tp1_hit               = reason == "tp_hit"
            trade.exit_commission       = round(exit_commission, 8)
            trade.exit_role             = exit_role
            trade.total_commission      = round(total_commission, 8)
            trade.realized_pnl_exchange = round(realized_pnl, 8)
            try:
                import json
                from trade.health_monitor import get_health_from_redis
                health = get_health_from_redis(trade.coin)
                if health:
                    trade.health_at_close = json.dumps({
                        "state":    health.get("state"),
                        "failures": health.get("failures", []),
                        "warnings": health.get("warnings", []),
                    })
            except Exception:
                pass
            if trade.signal_id:
                sig = db.query(SignalModel).filter(SignalModel.id == trade.signal_id).first()
                if sig:
                    sig.outcome    = trade.outcome
                    sig.pnl        = pnl
                    sig.exit_price = exit_price
            log.info(
                "Trade closed: id:%s exit:%.6f pnl:%.4f fee:$%.6f reason:%s tp1:%s",
                trade_id, exit_price, pnl, total_commission, reason, trade.tp1_hit,
            )
    except Exception as e:
        log.error("_mark_closed error: %s", e)


async def open_position(
    coin:      str,
    direction: str,
    entry:     float,
    sl:        float,
    tp:        float,
    stake:     float,
    leverage:  int,
    signal_id: int | None = None,
    grade:     str        = "",
    regime:    str        = "",
    session:   str        = "",
    score:     float      = 0.0,
) -> dict:
    symbol   = f"{coin}USDT"
    is_short = direction == "SHORT"
    side     = "SELL" if is_short else "BUY"
    sl_side  = "BUY"  if is_short else "SELL"
    tp_side  = "BUY"  if is_short else "SELL"

    try:
        current = await get_ticker_price(symbol)
        if not current:
            return {"success": False, "error": "Could not fetch price"}

        ok, reason = _deviation_check(entry, current, sl, direction)
        if not ok:
            return {"success": False, "error": reason, "deviation_rejected": True}

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
            log.warning("Position already exists on exchange for %s — skipping", coin)
            return {"success": False, "error": f"Position already exists on Binance for {coin}"}

        await set_margin_mode(symbol, "ISOLATED")
        await set_leverage(symbol, leverage)

        prec            = await get_symbol_precision(symbol)
        qty_step        = prec.get("step_size",       0.001)
        min_qty         = prec.get("min_qty",         0.001)
        price_precision = prec.get("price_precision", 2)
        quantity        = _round_step((stake * leverage) / current, qty_step)

        if quantity < min_qty:
            return {"success": False, "error": f"Quantity {quantity} below minimum"}

        log.info("Opening: %s %s price:%.6f qty:%s stake:%.2f lev:%dx", coin, direction, current, quantity, stake, leverage)

        raw        = await _place_with_retry(symbol=symbol, side=side, order_type="MARKET", quantity=quantity)
        filled     = await _wait_for_fill(symbol, raw["orderId"])
        fill_price = float(filled.get("avgPrice") or filled.get("price") or current)
        filled_qty = _round_step(float(filled.get("executedQty", quantity)), qty_step)
        entry_oid  = str(filled.get("orderId", ""))
        actual_position_size = round(filled_qty * fill_price, 4)
        actual_margin        = round(actual_position_size / leverage, 4)

        log.info("Entry filled: %s %.6f qty:%s", coin, fill_price, filled_qty)

        await asyncio.sleep(5.0)

        comm         = await _get_commission(symbol, entry_oid)
        entry_fee    = float(comm.get("commission", 0))
        entry_role   = comm.get("role", "taker")
        slippage_pct = abs(fill_price - entry) / entry * 100 if entry > 0 else 0.0

        sl_oid = await _place_sl(symbol, sl_side, sl, price_precision)
        tp_oid = await _place_tp(symbol, tp_side, tp, price_precision)

        trade_id = _save_trade(
            coin               = coin,
            direction          = direction,
            signal_id          = signal_id,
            grade              = grade,
            entry_price        = fill_price,
            sl_price           = sl,
            tp1_price          = tp,
            position_size      = actual_position_size,
            margin_used        = actual_margin,
            leverage           = leverage,
            sl_order_id        = sl_oid,
            tp1_order_id       = tp_oid,
            entry_order_id     = entry_oid,
            regime             = regime,
            session            = session,
            score              = score,
            actual_fill_entry  = fill_price,
            slippage_entry_pct = round(slippage_pct, 4),
            entry_commission   = entry_fee,
            entry_role         = entry_role,
        )

        from alerts.telegram import send
        mode      = "DEMO" if cfg.TRADING_MODE != "live" else "LIVE"
        emoji     = "📈" if direction == "LONG" else "📉"
        sl_status = "✅" if sl_oid else "⚠️ FAILED — place manually"
        tp_status = "✅" if tp_oid else "⚠️ Failed"

        await send(
            f"{emoji} *{coin} {direction} Opened — {mode}*\n\n"
            f"Entry:   `${fill_price:.{price_precision}f}` (signal `${entry:.{price_precision}f}` slip `{slippage_pct:.3f}%`)\n"
            f"SL:      `${round(sl, price_precision)}` {sl_status}\n"
            f"TP:      `${round(tp, price_precision)}` {tp_status}\n"
            f"Stake:   `${stake:.2f}` × `{leverage}x` = `${stake*leverage:.2f}`\n"
            f"Fee:     `${entry_fee:.4f}` ({entry_role})\n"
            f"Grade:   `{grade}` · Score `{score}`\n"
            f"Regime:  `{regime}` · Session `{session}`"
        )

        return {
            "success":    True,
            "trade_id":   trade_id,
            "fill_price": fill_price,
            "quantity":   filled_qty,
            "sl_order":   sl_oid,
            "tp_order":   tp_oid,
            "commission": entry_fee,
            "role":       entry_role,
        }

    except Exception as e:
        log.error("open_position %s: %s", coin, e, exc_info=True)
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
            (p for p in positions if p.get("symbol") == symbol and float(p.get("positionAmt", 0)) != 0),
            None,
        )

        if not position:
            log.warning("No open position for %s", coin)
            _mark_closed(trade_id, 0.0, 0.0, reason)
            return {"success": False, "error": "No open position found"}

        await _cleanup_orders(symbol)

        qty        = abs(float(position.get("positionAmt", 0)))
        close_side = "BUY" if is_short else "SELL"

        raw        = await _place_with_retry(symbol=symbol, side=close_side, order_type="MARKET", quantity=qty, reduce_only=True)
        filled     = await _wait_for_fill(symbol, raw["orderId"])
        close_oid  = str(filled.get("orderId", ""))
        exit_price = float(filled.get("avgPrice") or filled.get("price") or 0)

        await asyncio.sleep(2.0)
        comm            = await _get_commission(symbol, close_oid)
        exit_fee        = float(comm.get("commission",   0))
        exit_role       = comm.get("role", "taker")
        realized_pnl    = float(comm.get("realized_pnl", 0))
        entry_fee       = _get_field(trade_id, "entry_commission")
        total_fee       = round(entry_fee + exit_fee, 8)

        sl_price        = _get_field(trade_id, "sl_price")
        tp_price        = _get_field(trade_id, "tp1_price")
        slippage_exit   = 0.0
        if reason == "tp_hit" and tp_price:
            slippage_exit = abs(exit_price - tp_price) / tp_price * 100
        elif reason == "sl_hit" and sl_price:
            slippage_exit = abs(exit_price - sl_price) / sl_price * 100

        net_pnl = (
            round(realized_pnl - exit_fee, 8) if realized_pnl != 0
            else _calc_pnl(
                direction  = direction,
                entry      = _get_field(trade_id, "entry_price"),
                exit_price = exit_price,
                margin     = _get_field(trade_id, "margin_used"),
                leverage   = int(_get_field(trade_id, "leverage") or 1),
                commission = total_fee,
            )
        )

        _mark_closed(
            trade_id          = trade_id,
            exit_price        = exit_price,
            pnl               = net_pnl,
            reason            = reason,
            exit_commission   = exit_fee,
            exit_role         = exit_role,
            total_commission  = total_fee,
            realized_pnl      = realized_pnl,
            slippage_exit_pct = slippage_exit,
        )

        from alerts.telegram import send
        emoji   = "✅" if net_pnl >= 0 else "❌"
        pnl_str = f"+${net_pnl:.4f}" if net_pnl >= 0 else f"-${abs(net_pnl):.4f}"
        await send(
            f"{emoji} *{coin} {direction} Closed*\n\n"
            f"Exit:   `${exit_price:.6f}`\n"
            f"PnL:    `{pnl_str}`\n"
            f"Fee:    `${total_fee:.4f}` ({exit_role})\n"
            f"Reason: `{reason}`"
        )

        return {"success": True, "exit_price": exit_price, "pnl": net_pnl}

    except Exception as e:
        log.error("close_position %s: %s", coin, e, exc_info=True)
        return {"success": False, "error": str(e)}


def has_open_trade(coin: str) -> bool:
    try:
        with get_session() as db:
            return db.query(TradeModel).filter(
                TradeModel.coin == coin, TradeModel.is_active == True
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