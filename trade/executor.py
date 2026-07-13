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

CLOSE_REASONS = {
    "tp1_hit":                 "Take profit 1 reached",
    "tp2_hit":                 "Take profit 2 reached",
    "sl_hit":                  "Stop loss triggered",
    "tp1_be_stop":             "Breakeven stop triggered after TP1",
    "time_stop_profit":        "Time stop — position profitable at expiry",
    "time_stop_breakeven":     "Time stop — position at breakeven at expiry",
    "time_stop_loss":          "Time stop — position adverse within SL tolerance",
    "time_stop_after_tp1":     "Time stop — TP1 hit, TP2 not reached in window",
    "close_before_asia":       "Session close — avoiding Asia session with adverse position",
    "manual_dashboard_close":  "Dashboard force close by operator",
    "exchange_closed":         "Position closed on exchange — reason unknown",
    "liquidated":              "Liquidation triggered",
    "deviation_rejected":      "Entry rejected — price moved too far from signal",
    "thesis_invalidated":      "Thesis invalidated — structural conditions broken",
    "thesis_degraded":         "Thesis degraded — majority of pillars failed",
}


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
    price_precision: int   = 8,
    tick_size:       float = 0.0,
) -> str | None:
    if tick_size and tick_size > 0:
        sl = _round_tick(sl, tick_size)

    log.info("Placing SL: %s side:%s price:%s", symbol, side, sl)

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
        if algo_id and algo_id != "0":
            log.info("SL placed: %s sl:%s algoId:%s", symbol, sl, algo_id)
            return algo_id
    except Exception as e:
        log.error("SL algo order failed %s: %s", symbol, e)
        from alerts.telegram import send
        coin = symbol.replace("USDT", "")
        await send(
            f"⚠️ *SL Order Failed — {coin}*\n\n"
            f"Could not place SL at `{sl}`\n"
            f"Position is unprotected — place SL manually immediately."
        )
        return None


async def _place_tp_partial(
    symbol:          str,
    side:            str,
    tp:              float,
    quantity:        float,
    step_size:       float = 0.0,
    tick_size:       float = 0.0,
    price_precision: int   = 8,
    label:           str   = "TP",
) -> str | None:
    if tick_size  and tick_size  > 0: tp       = _round_tick(tp,       tick_size)
    if step_size  and step_size  > 0: quantity = _round_step(quantity, step_size)

    if quantity <= 0:
        log.warning("_place_tp_partial: quantity zero for %s %s", symbol, label)
        return None

    log.info("Placing %s: %s side:%s price:%s qty:%s", label, symbol, side, tp, quantity)

    try:
        order   = await place_algo_order(
            symbol          = symbol,
            side            = side,
            order_type      = "TAKE_PROFIT_MARKET",
            trigger_price   = tp,
            price_precision = price_precision,
            close_position  = False,
            quantity        = quantity,
        )
        algo_id = str(order.get("algoId", ""))
        if algo_id and algo_id != "0":
            log.info("%s placed: %s tp:%s qty:%s algoId:%s", label, symbol, tp, quantity, algo_id)
            return algo_id
    except Exception as e:
        log.error("%s algo order failed %s: %s", label, symbol, e)
        return None


async def move_sl_to_breakeven(
    symbol:          str,
    side:            str,
    entry_price:     float,
    atr_15m:         float,
    price_precision: int   = 8,
    tick_size:       float = 0.0,
    is_long:         bool  = True,
) -> str | None:
    try:
        await cancel_all_orders(symbol)
        await cancel_all_algo_orders(symbol)
        await asyncio.sleep(1.0)

        buffer   = atr_15m * 0.1
        be_price = entry_price + buffer if is_long else entry_price - buffer

        if tick_size and tick_size > 0:
            be_price = _round_tick(be_price, tick_size)

        log.info("Moving SL to breakeven: %s be_price:%s", symbol, be_price)

        try:
            order   = await place_algo_order(
                symbol          = symbol,
                side            = side,
                order_type      = "STOP_MARKET",
                trigger_price   = be_price,
                price_precision = price_precision,
                close_position  = True,
            )
            algo_id = str(order.get("algoId", ""))
            if algo_id and algo_id != "0":
                log.info("BE SL placed: %s be:%s algoId:%s", symbol, be_price, algo_id)
                return algo_id
        except Exception as e:
            log.error("BE SL algo order failed %s: %s", symbol, e)
            return None

    except Exception as e:
        log.error("move_sl_to_breakeven %s: %s", symbol, e)
        return None


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


def _create_pending_trade(
    coin:          str,
    direction:     str,
    signal_id:     int | None,
    grade:         str,
    sl_price:      float,
    tp1_price:     float,
    tp2_price:     float | None,
    leverage:      int,
    regime:        str   = "",
    session:       str   = "",
    score:         float = 0.0,
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
    position_size:      float,
    margin_used:        float,
    sl_order_id:        str | None,
    tp1_order_id:       str | None,
    tp2_order_id:       str | None,
    entry_order_id:     str,
    actual_fill_entry:  float = 0.0,
    slippage_entry_pct: float = 0.0,
    entry_commission:   float = 0.0,
    entry_role:         str   = "taker",
    tp1_qty:            float = 0.0,
    tp2_qty:            float = 0.0,
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
            trade.position_size      = position_size
            trade.margin_used        = margin_used
            trade.sl_order_id        = sl_order_id
            trade.tp1_order_id       = tp1_order_id
            trade.tp2_order_id       = tp2_order_id
            trade.entry_order_id     = entry_order_id
            trade.balance_at_open    = margin_used
            trade.actual_fill_entry  = actual_fill_entry or entry_price
            trade.slippage_entry_pct = slippage_entry_pct
            trade.entry_commission   = entry_commission
            trade.entry_role         = entry_role
            trade.funding_fees_paid  = 0.0
            trade.total_commission   = entry_commission
            trade.notes              = f"tp1_qty:{tp1_qty:.6f} tp2_qty:{tp2_qty:.6f}"

            if sizing_result:
                trade.drawdown_at_entry    = sizing_result.get("drawdown_pct")
                trade.win_rate_at_entry    = sizing_result.get("win_rate")
                trade.streak_at_entry      = sizing_result.get("streak")
                trade.streak_type_at_entry = sizing_result.get("streak_type")
                trade.daily_pnl_at_entry   = sizing_result.get("today_pnl")
                trade.open_trades_at_entry = sizing_result.get("open_trades")

            log.info(
                "Trade activated: id:%s fill:%.6f slip:%.4f%% fee:$%.8f drawdown:%.2f%% wr:%s",
                trade_id, actual_fill_entry, slippage_entry_pct, entry_commission,
                sizing_result.get("drawdown_pct", 0) if sizing_result else 0,
                sizing_result.get("win_rate", "N/A") if sizing_result else "N/A",
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
            trade.tp1_hit               = reason in (
                "tp1_hit", "tp2_hit", "tp1_be_stop", "time_stop_after_tp1"
            )
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

            try:
                from trade.thesis_tracker import get_thesis, get_pillar_states_json
                thesis = get_thesis(trade_id)
                if thesis:
                    trade.thesis_strength_at_close  = thesis.thesis_strength
                    trade.thesis_pillars_at_close   = get_pillar_states_json(trade_id)
                    trade.thesis_exit_reason        = thesis.action_reason
                    trade.captured_move_pct_at_exit = thesis.captured_move_pct
                    trade.expected_move_pct         = thesis.expected_move_pct
                    trade.velocity_at_close         = thesis.velocity
            except Exception:
                pass

            if trade.signal_id:
                sig = db.query(SignalModel).filter(SignalModel.id == trade.signal_id).first()
                if sig:
                    sig.outcome    = trade.outcome
                    sig.pnl        = pnl
                    sig.exit_price = exit_price

            log.info(
                "Trade closed: id:%s exit:%.6f pnl:%.4f fee:$%.8f reason:%s tp1:%s",
                trade_id, exit_price, pnl, total_commission, reason, trade.tp1_hit,
            )
    except Exception as e:
        log.error("_mark_closed error: %s", e)


def _mark_tp1_hit(trade_id: int, partial_pnl: float, new_sl_order_id: str | None) -> None:
    try:
        with get_session() as db:
            trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if not trade:
                return
            trade.tp1_hit     = True
            trade.partial_pnl = partial_pnl
            trade.sl_price    = trade.entry_price
            if new_sl_order_id:
                trade.sl_order_id = new_sl_order_id
            log.info("TP1 hit recorded: id:%s partial_pnl:%.4f", trade_id, partial_pnl)
    except Exception as e:
        log.error("_mark_tp1_hit error: %s", e)


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

    SE = cfg.SCALP_ENGINE

    trade_id = 0

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
            return {"success": False, "error": f"Position already exists on exchange for {coin}"}

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

        log.info(
            "Precision %s: tick=%.10f price_prec=%d step=%.10f",
            coin, tick_size, price_precision, qty_step
        )

        total_quantity = _round_step((stake * leverage) / current, qty_step)

        if min_qty > 0 and total_quantity < min_qty:
            _cancel_pending_trade(trade_id)
            return {"success": False, "error": f"Quantity {total_quantity} below minimum {min_qty}"}

        tp1_qty_final = _round_step(total_quantity * SE["tp1_close_pct"], qty_step)
        tp2_qty_final = _round_step(total_quantity * SE["tp2_close_pct"], qty_step)

        if tp1_qty_final <= 0:
            tp1_qty_final = total_quantity
            tp2_qty_final = 0.0

        if tp2_qty_final > 0 and tp1_qty_final + tp2_qty_final > total_quantity:
            tp2_qty_final = _round_step(total_quantity - tp1_qty_final, qty_step)

        sl_rounded  = _round_tick(sl,  tick_size)
        tp1_rounded = _round_tick(tp,  tick_size)
        tp2_rounded = _round_tick(tp2, tick_size) if tp2 else None

        log.info(
            "Opening: %s %s price:%.6f qty:%s tp1_qty:%s tp2_qty:%s "
            "stake:%.2f lev:%dx sl:%s tp1:%s tp2:%s",
            coin, direction, current, total_quantity, tp1_qty_final, tp2_qty_final,
            stake, leverage, sl_rounded, tp1_rounded, tp2_rounded
        )

        raw        = await _place_with_retry(symbol=symbol, side=side, order_type="MARKET", quantity=total_quantity)
        filled     = await _wait_for_fill(symbol, raw["orderId"])
        fill_price = float(filled.get("avgPrice") or filled.get("price") or current)
        filled_qty = _round_step(float(filled.get("executedQty", total_quantity)), qty_step)
        entry_oid  = str(filled.get("orderId", ""))

        actual_position_size = round(filled_qty * fill_price, 8)
        actual_margin        = round(actual_position_size / leverage, 8)

        log.info("Entry filled: %s %.6f qty:%s", coin, fill_price, filled_qty)

        await asyncio.sleep(5.0)

        comm         = await _get_commission(symbol, entry_oid)
        entry_fee    = float(comm.get("commission", 0))
        entry_role   = comm.get("role", "taker")
        slippage_pct = abs(fill_price - entry) / entry * 100 if entry > 0 else 0.0

        tp1_qty_final = _round_step(filled_qty * SE["tp1_close_pct"], qty_step)
        tp2_qty_final = _round_step(filled_qty * SE["tp2_close_pct"], qty_step)

        if tp1_qty_final <= 0:
            tp1_qty_final = filled_qty
            tp2_qty_final = 0.0

        if tp2_qty_final > 0 and tp1_qty_final + tp2_qty_final > filled_qty:
            tp2_qty_final = _round_step(filled_qty - tp1_qty_final, qty_step)

        sl_oid  = await _place_sl(symbol, sl_side, sl_rounded, price_precision, tick_size)

        tp1_oid = await _place_tp_partial(
            symbol          = symbol,
            side            = tp_side,
            tp              = tp1_rounded,
            quantity        = tp1_qty_final,
            step_size       = qty_step,
            tick_size       = tick_size,
            price_precision = price_precision,
            label           = "TP1",
        )

        tp2_oid = None
        if tp2_rounded and tp2_qty_final > 0:
            tp2_oid = await _place_tp_partial(
                symbol          = symbol,
                side            = tp_side,
                tp              = tp2_rounded,
                quantity        = tp2_qty_final,
                step_size       = qty_step,
                tick_size       = tick_size,
                price_precision = price_precision,
                label           = "TP2",
            )

        if not atr_15m or atr_15m <= 0:
            atr_15m = fill_price * 0.005

        _activate_trade(
            trade_id           = trade_id,
            entry_price        = fill_price,
            position_size      = actual_position_size,
            margin_used        = actual_margin,
            sl_order_id        = sl_oid,
            tp1_order_id       = tp1_oid,
            tp2_order_id       = tp2_oid,
            entry_order_id     = entry_oid,
            actual_fill_entry  = fill_price,
            slippage_entry_pct = round(slippage_pct, 4),
            entry_commission   = entry_fee,
            entry_role         = entry_role,
            tp1_qty            = tp1_qty_final,
            tp2_qty            = tp2_qty_final,
            sizing_result      = sizing_result,
        )

        from trade.exit_manager import initialize_thesis_for_trade
        signal_data = {
            "sweep_score":   float(sizing_result.get("sweep_score",   0) if sizing_result else 0),
            "zone_score":    float(sizing_result.get("zone_score",    0) if sizing_result else 0),
            "trigger_score": float(sizing_result.get("trigger_score", 0) if sizing_result else 0),
            "grade":         grade,
            "score":         score,
        }
        trade_dict = {
            "id":               trade_id,
            "coin":             coin,
            "direction":        direction,
            "grade":            grade,
            "entry_price":      fill_price,
            "sl_price":         sl,
            "tp1_price":        tp,
            "tp2_price":        tp2,
            "regime_at_entry":  regime,
            "session_at_entry": session,
            "signal_id":        signal_id,
        }
        asyncio.create_task(initialize_thesis_for_trade(trade_dict, signal_data))

        from ml.version_registry import tag_trade
        tag_trade(trade_id)

        from alerts.telegram import send
        mode      = "DEMO" if cfg.TRADING_MODE != "live" else "LIVE"
        emoji     = "📈" if direction == "LONG" else "📉"
        sl_status = "✅" if sl_oid  else "⚠️ FAILED"
        t1_status = "✅" if tp1_oid else "⚠️ Failed"
        t2_status = "✅" if tp2_oid else "—" if not tp2_rounded else "⚠️ Failed"

        await send(
            f"{emoji} *{coin} {direction} Opened — {mode}*\n\n"
            f"Entry:   `{fill_price}` (signal `{entry}` slip `{slippage_pct:.4f}%`)\n"
            f"SL:      `{sl_rounded}` {sl_status}\n"
            f"TP1:     `{tp1_rounded}` qty:`{tp1_qty_final}` {t1_status}\n"
            f"TP2:     `{tp2_rounded or 'none'}` qty:`{tp2_qty_final}` {t2_status}\n"
            f"Stake:   `${stake:.2f}` × `{leverage}x` = `${stake*leverage:.2f}`\n"
            f"Fee:     `${entry_fee:.8f}` ({entry_role})\n"
            f"Grade:   `{grade}` · Score `{score}`"
        )

        return {
            "success":    True,
            "trade_id":   trade_id,
            "fill_price": fill_price,
            "quantity":   filled_qty,
            "tp1_qty":    tp1_qty_final,
            "tp2_qty":    tp2_qty_final,
            "sl_order":   sl_oid,
            "tp1_order":  tp1_oid,
            "tp2_order":  tp2_oid,
            "commission": entry_fee,
            "role":       entry_role,
            "atr_15m":    atr_15m,
        }

    except Exception as e:
        log.error("open_position %s: %s", coin, e, exc_info=True)
        if trade_id:
            _cancel_pending_trade(trade_id)
        return {"success": False, "error": str(e)}


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

        prec      = await get_symbol_precision(symbol)
        qty_step  = prec["step_size"]
        qty       = _round_step(qty, qty_step)

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
            round(realized_pnl - total_fee, 8) if realized_pnl != 0
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

        try:
            from ml.outcome_recorder import record
            asyncio.create_task(record(trade_id))
        except Exception as _oe:
            log.error("outcome_recorder failed trade_id=%s: %s", trade_id, _oe)

        from alerts.telegram import send
        emoji        = "✅" if net_pnl >= 0 else "❌"
        pnl_str      = f"+${net_pnl:.4f}" if net_pnl >= 0 else f"-${abs(net_pnl):.4f}"
        reason_label = CLOSE_REASONS.get(reason, reason)
        await send(
            f"{emoji} *{coin} {direction} Closed*\n\n"
            f"Exit:   `{exit_price}`\n"
            f"PnL:    `{pnl_str}`\n"
            f"Fee:    `${total_fee:.8f}` ({exit_role})\n"
            f"Reason: `{reason_label}`"
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
                TradeModel.is_active == True
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