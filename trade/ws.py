import asyncio
import json
import logging
import time
import websockets
from datetime import datetime, timezone
from trade.exchange import (
    get_listen_key, refresh_listen_key,
    invalidate_listen_key, get_ws_base_url
)
from config import cfg

log = logging.getLogger(__name__)

_mark_prices:          dict         = {}
_ws_task:              asyncio.Task = None
_user_ws_task:         asyncio.Task = None
_listen_key_task:      asyncio.Task = None
_ws_connected:         bool         = False
_user_ws_connected:    bool         = False

_trade_event_callbacks = []

_pending_commissions:  dict         = {}


def on_trade_event(callback):
    if callback not in _trade_event_callbacks:
        _trade_event_callbacks.append(callback)


def get_mark_price(coin: str) -> float:
    symbol = f"{coin}USDT"
    return _mark_prices.get(symbol, 0.0)


def get_all_mark_prices() -> dict:
    return dict(_mark_prices)


def is_connected() -> bool:
    return _ws_connected and _user_ws_connected


def get_pending_commission(order_id: str) -> dict | None:
    return _pending_commissions.get(str(order_id))


def clear_pending_commission(order_id: str):
    _pending_commissions.pop(str(order_id), None)


async def _emit_trade_event(event_type: str, data: dict):
    for cb in _trade_event_callbacks:
        try:
            await cb(event_type, data)
        except Exception as e:
            log.error(f"Trade event callback error: {e}")


async def _mark_price_stream():
    global _ws_connected
    ws_base = get_ws_base_url()

    while True:
        try:
            url = f"{ws_base}/ws/!markPrice@arr@1s"
            log.info(f"Mark price WS connecting: {url[:50]}...")

            async with websockets.connect(
                url,
                ping_interval = 20,
                ping_timeout  = 10,
                close_timeout = 5,
                open_timeout  = 15,
            ) as ws:
                _ws_connected = True
                log.info("Mark price WS connected ✅")

                async for message in ws:
                    try:
                        data = json.loads(message)
                        if isinstance(data, list):
                            for item in data:
                                symbol = item.get("s", "")
                                price  = float(item.get("p", 0))
                                if symbol and price:
                                    _mark_prices[symbol] = price
                        elif isinstance(data, dict):
                            symbol = data.get("s", "")
                            price  = float(data.get("p", 0))
                            if symbol and price:
                                _mark_prices[symbol] = price
                    except Exception as e:
                        log.debug(f"Mark price parse error: {e}")

        except websockets.exceptions.ConnectionClosedError as e:
            _ws_connected = False
            log.warning(f"Mark price WS closed: {e} — retrying in 5s")
            await asyncio.sleep(5)
        except Exception as e:
            _ws_connected = False
            log.warning(f"Mark price WS error: {e} — retrying in 5s")
            await asyncio.sleep(5)


async def _user_data_stream():
    global _user_ws_connected
    ws_base = get_ws_base_url()

    while True:
        try:
            listen_key = await get_listen_key()
            if not listen_key:
                log.warning("No listen key — retrying in 10s")
                await asyncio.sleep(10)
                continue

            url = f"{ws_base}/ws/{listen_key}"
            log.info(f"User data WS connecting...")

            async with websockets.connect(
                url,
                ping_interval = 20,
                ping_timeout  = 10,
                close_timeout = 5,
                open_timeout  = 15,
            ) as ws:
                _user_ws_connected = True
                log.info("User data WS connected ✅")

                async for message in ws:
                    try:
                        data       = json.loads(message)
                        event_type = data.get("e", "")

                        if event_type == "ORDER_TRADE_UPDATE":
                            await _handle_order_update(data)

                        elif event_type == "ACCOUNT_UPDATE":
                            await _handle_account_update(data)

                        elif event_type == "listenKeyExpired":
                            log.warning("Listen key expired — reconnecting")
                            _user_ws_connected = False
                            break

                    except Exception as e:
                        log.error(f"User data WS parse error: {e}")

        except websockets.exceptions.ConnectionClosedError as e:
            _user_ws_connected = False
            log.warning(f"User data WS closed: {e} — retrying in 5s")
            await asyncio.sleep(5)
        except Exception as e:
            _user_ws_connected = False
            log.warning(f"User data WS error: {e} — retrying in 10s")
            await asyncio.sleep(10)


async def _handle_order_update(data: dict):
    try:
        order = data.get("o", {})

        symbol       = order.get("s", "")
        coin         = symbol.replace("USDT", "")
        order_id     = str(order.get("i", ""))
        status       = order.get("X", "")
        order_type   = order.get("o", "")
        side         = order.get("S", "")
        avg_price    = float(order.get("ap", 0) or order.get("p", 0))
        filled_qty   = float(order.get("z", 0))
        reduce_only  = order.get("R", False)
        close_pos    = order.get("cp", False)
        commission   = float(order.get("n", 0) or 0)
        comm_asset   = order.get("N", "USDT") or "USDT"
        is_maker     = order.get("m", False)
        realized_pnl = float(order.get("rp", 0) or 0)

        log.info(
            f"Order update: {coin} {side} {order_type} "
            f"status:{status} price:{avg_price} qty:{filled_qty} "
            f"commission:{commission} {comm_asset} "
            f"role:{'maker' if is_maker else 'taker'} "
            f"realized_pnl:{realized_pnl}"
        )

        if status == "FILLED":
            _pending_commissions[order_id] = {
                "commission":       commission,
                "commission_asset": comm_asset,
                "role":             "maker" if is_maker else "taker",
                "realized_pnl":     realized_pnl,
                "avg_price":        avg_price,
                "filled_qty":       filled_qty,
                "coin":             coin,
                "order_type":       order_type,
                "side":             side,
                "timestamp":        time.time(),
            }

            if reduce_only or close_pos:
                await _handle_position_closed(
                    coin         = coin,
                    exit_price   = avg_price,
                    order_id     = order_id,
                    order_type   = order_type,
                    side         = side,
                    commission   = commission,
                    comm_asset   = comm_asset,
                    is_maker     = is_maker,
                    realized_pnl = realized_pnl,
                )
            else:
                await _emit_trade_event("order_filled", {
                    "coin":             coin,
                    "order_id":         order_id,
                    "side":             side,
                    "price":            avg_price,
                    "quantity":         filled_qty,
                    "order_type":       order_type,
                    "commission":       commission,
                    "commission_asset": comm_asset,
                    "role":             "maker" if is_maker else "taker",
                    "realized_pnl":     realized_pnl,
                })

    except Exception as e:
        log.error(f"_handle_order_update error: {e}")


async def _handle_position_closed(
    coin:         str,
    exit_price:   float,
    order_id:     str,
    order_type:   str,
    side:         str,
    commission:   float = 0.0,
    comm_asset:   str   = "USDT",
    is_maker:     bool  = False,
    realized_pnl: float = 0.0,
):
    try:
        from database import get_session, Trade as TradeModel, Signal as SignalModel
        from trade.monitor import invalidate_position_cache
        from trade.health_monitor import clear_health_state

        with get_session() as db:
            trade = db.query(TradeModel).filter(
                TradeModel.coin      == coin,
                TradeModel.is_active == True,
            ).first()

            if not trade:
                log.debug(f"No active trade found for {coin} — may already be closed")
                return

            trade_id         = trade.id
            direction        = trade.direction
            entry            = float(trade.entry_price or 0)
            margin           = float(trade.margin_used or 0)
            leverage         = int(trade.leverage or 1)
            entry_commission = float(trade.entry_commission or 0)
            signal_entry     = entry

            exit_reason = _determine_exit_reason_from_order(
                order_type = order_type,
                order_id   = order_id,
                trade_sl   = str(trade.sl_order_id or ""),
                trade_tp   = str(trade.tp1_order_id or ""),
            )

            total_commission = round(entry_commission + commission, 8)

            if realized_pnl != 0:
                net_pnl = round(realized_pnl - commission, 8)
            else:
                TAKER_FEE = 0.0005
                position  = margin * leverage
                if direction == "LONG":
                    gross = (exit_price - entry) / entry * position
                else:
                    gross = (entry - exit_price) / entry * position
                net_pnl = round(gross - total_commission, 4)

            slippage_exit_pct = 0.0
            if exit_reason == "tp_hit" and trade.tp1_price:
                slippage_exit_pct = abs(exit_price - float(trade.tp1_price)) / float(trade.tp1_price) * 100
            elif exit_reason == "sl_hit" and trade.sl_price:
                slippage_exit_pct = abs(exit_price - float(trade.sl_price)) / float(trade.sl_price) * 100

            health_at_close = None
            try:
                from trade.health_monitor import get_health_from_redis
                health = get_health_from_redis(coin)
                if health:
                    health_at_close = json.dumps({
                        "state":    health.get("state"),
                        "failures": health.get("failures", []),
                        "warnings": health.get("warnings", []),
                    })
            except Exception:
                pass

            trade.is_active            = False
            trade.state                = "closed"
            trade.exit_price           = exit_price
            trade.actual_fill_exit     = exit_price
            trade.slippage_exit_pct    = round(slippage_exit_pct, 4)
            trade.exit_commission      = round(commission, 8)
            trade.exit_role            = "maker" if is_maker else "taker"
            trade.total_commission     = total_commission
            trade.realized_pnl_exchange= round(realized_pnl, 8)
            trade.net_pnl              = net_pnl
            trade.pnl                  = net_pnl
            trade.close_reason         = exit_reason
            trade.closed_at            = datetime.now(timezone.utc)
            trade.outcome              = "win" if net_pnl > 0 else "loss"
            trade.tp1_hit              = exit_reason == "tp_hit"
            trade.health_at_close      = health_at_close

            if trade.signal_id:
                sig = db.query(SignalModel).filter(
                    SignalModel.id == trade.signal_id
                ).first()
                if sig:
                    sig.outcome    = trade.outcome
                    sig.pnl        = net_pnl
                    sig.exit_price = exit_price

        invalidate_position_cache()
        clear_health_state(coin)

        emoji   = "✅" if net_pnl >= 0 else "❌"
        pnl_str = f"+${net_pnl:.4f}" if net_pnl >= 0 else f"-${abs(net_pnl):.4f}"

        from alerts.telegram import send
        await send(
            f"{emoji} *{coin} {direction} Closed*\n\n"
            f"Reason:      `{exit_reason}`\n"
            f"Exit:        `${exit_price:.6f}`\n"
            f"Net PnL:     `{pnl_str}`\n"
            f"Commission:  `${total_commission:.4f}`\n"
            f"Role:        `{'maker' if is_maker else 'taker'}`\n"
            f"Realized:    `${realized_pnl:.4f}` (exchange)"
        )

        await _emit_trade_event("trade_closed", {
            "coin":        coin,
            "direction":   direction,
            "exit_price":  exit_price,
            "net_pnl":     net_pnl,
            "commission":  total_commission,
            "reason":      exit_reason,
        })

        from events import emit
        asyncio.create_task(emit("trade_closed", {
            "coin":      coin,
            "direction": direction,
            "pnl":       net_pnl,
            "reason":    exit_reason,
        }))

        log.info(
            f"Position closed via WS: {coin} {direction} "
            f"exit:{exit_price} net_pnl:{net_pnl} "
            f"commission:{total_commission} reason:{exit_reason}"
        )

    except Exception as e:
        log.error(f"_handle_position_closed error {coin}: {e}", exc_info=True)


def _determine_exit_reason_from_order(
    order_type: str,
    order_id:   str,
    trade_sl:   str,
    trade_tp:   str,
) -> str:
    ot = order_type.upper()

    if "STOP" in ot:
        return "sl_hit"

    if ot == "LIMIT":
        if trade_tp and str(order_id) == str(trade_tp):
            return "tp_hit"
        return "tp_hit"

    if ot == "MARKET":
        return "manual_close"

    if "LIQUIDATION" in ot:
        return "liquidated"

    return "exchange_closed"


async def _handle_account_update(data: dict):
    try:
        account   = data.get("a", {})
        balances  = account.get("B", [])
        positions = account.get("P", [])

        for b in balances:
            if b.get("a") == "USDT":
                log.debug(f"Balance update: {b.get('wb')} USDT")

        for p in positions:
            symbol = p.get("s", "")
            amt    = float(p.get("pa", 0))
            pnl    = float(p.get("up", 0))
            log.debug(f"Position update: {symbol} amt:{amt} upnl:{pnl}")

        await _emit_trade_event("account_update", {
            "balances":  balances,
            "positions": positions,
        })

    except Exception as e:
        log.error(f"_handle_account_update error: {e}")


async def _listen_key_refresh_loop():
    while True:
        await asyncio.sleep(1200)
        try:
            success = await refresh_listen_key()
            if not success:
                log.warning("Listen key refresh failed — will reconnect")
        except Exception as e:
            log.error(f"Listen key refresh loop error: {e}")


async def start_ws():
    global _ws_task, _user_ws_task, _listen_key_task

    if _ws_task and not _ws_task.done():
        return

    _ws_task         = asyncio.create_task(_mark_price_stream())
    _user_ws_task    = asyncio.create_task(_user_data_stream())
    _listen_key_task = asyncio.create_task(_listen_key_refresh_loop())

    log.info("Binance WebSocket streams started")


async def stop_ws():
    global _ws_task, _user_ws_task, _listen_key_task
    global _ws_connected, _user_ws_connected

    for task in [_ws_task, _user_ws_task, _listen_key_task]:
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    _ws_task           = None
    _user_ws_task      = None
    _listen_key_task   = None
    _ws_connected      = False
    _user_ws_connected = False

    try:
        await invalidate_listen_key()
    except Exception:
        pass

    log.info("Binance WebSocket streams stopped")


def get_ws_status() -> dict:
    return {
        "mark_price_connected": _ws_connected,
        "user_data_connected":  _user_ws_connected,
        "prices_cached":        len(_mark_prices),
        "mode":                 cfg.TRADING_MODE,
    }