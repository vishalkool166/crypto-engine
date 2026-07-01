import asyncio
import json
import logging
import time
import websockets
from datetime import datetime, timezone
from trade.exchange import (
    get_listen_key, refresh_listen_key,
    invalidate_listen_key, get_ws_base_url,
)
from config import cfg

log = logging.getLogger(__name__)

_mark_prices:         dict          = {}
_ws_task:             asyncio.Task | None = None
_user_ws_task:        asyncio.Task | None = None
_listen_key_task:     asyncio.Task | None = None
_ws_connected:        bool          = False
_user_ws_connected:   bool          = False
_pending_commissions: dict          = {}
_trade_event_callbacks: list        = []


def on_trade_event(callback) -> None:
    if callback not in _trade_event_callbacks:
        _trade_event_callbacks.append(callback)


def get_mark_price(coin: str) -> float:
    return _mark_prices.get(f"{coin}USDT", 0.0)


def get_all_mark_prices() -> dict:
    return dict(_mark_prices)


def is_connected() -> bool:
    return _ws_connected and _user_ws_connected


def get_pending_commission(order_id: str) -> dict | None:
    return _pending_commissions.get(str(order_id))


def clear_pending_commission(order_id: str) -> None:
    _pending_commissions.pop(str(order_id), None)


def get_ws_status() -> dict:
    return {
        "mark_price_connected": _ws_connected,
        "user_data_connected":  _user_ws_connected,
        "prices_cached":        len(_mark_prices),
        "mode":                 cfg.TRADING_MODE,
    }


async def _emit(event_type: str, data: dict) -> None:
    for cb in _trade_event_callbacks:
        try:
            await cb(event_type, data)
        except Exception as e:
            log.error("Trade event callback error: %s", e)


async def _mark_price_stream() -> None:
    global _ws_connected
    while True:
        try:
            url = f"{get_ws_base_url()}/ws/!markPrice@arr@1s"
            log.info("Mark price WS connecting: %s...", url[:50])
            async with websockets.connect(url, ping_interval=20, ping_timeout=10, open_timeout=15) as ws:
                _ws_connected = True
                log.info("Mark price WS connected ✅")
                async for message in ws:
                    try:
                        data = json.loads(message)
                        items = data if isinstance(data, list) else [data]
                        for item in items:
                            s = item.get("s", "")
                            p = float(item.get("p", 0))
                            if s and p:
                                _mark_prices[s] = p
                    except Exception:
                        pass
        except websockets.exceptions.ConnectionClosedError as e:
            _ws_connected = False
            log.warning("Mark price WS closed: %s — retry 5s", e)
        except Exception as e:
            _ws_connected = False
            log.warning("Mark price WS error: %s — retry 5s", e)
        await asyncio.sleep(5)


async def _user_data_stream() -> None:
    global _user_ws_connected
    while True:
        try:
            listen_key = await get_listen_key()
            if not listen_key:
                await asyncio.sleep(10)
                continue
            url = f"{get_ws_base_url()}/ws/{listen_key}"
            log.info("User data WS connecting...")
            async with websockets.connect(url, ping_interval=20, ping_timeout=10, open_timeout=15) as ws:
                _user_ws_connected = True
                log.info("User data WS connected ✅")
                async for message in ws:
                    try:
                        data = json.loads(message)
                        et   = data.get("e", "")
                        if et == "ORDER_TRADE_UPDATE":
                            await _handle_order_update(data)
                        elif et == "ACCOUNT_UPDATE":
                            await _handle_account_update(data)
                        elif et == "listenKeyExpired":
                            log.warning("Listen key expired — reconnecting")
                            _user_ws_connected = False
                            break
                    except Exception as e:
                        log.error("User data WS parse error: %s", e)
        except websockets.exceptions.ConnectionClosedError as e:
            _user_ws_connected = False
            log.warning("User data WS closed: %s — retry 5s", e)
        except Exception as e:
            _user_ws_connected = False
            log.warning("User data WS error: %s — retry 10s", e)
            await asyncio.sleep(5)
        await asyncio.sleep(5)


async def _handle_order_update(data: dict) -> None:
    try:
        order        = data.get("o", {})
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
            "Order update: %s %s %s status:%s price:%.6f qty:%s fee:%s role:%s rpnl:%s",
            coin, side, order_type, status, avg_price, filled_qty,
            commission, "maker" if is_maker else "taker", realized_pnl,
        )

        if status != "FILLED":
            return

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
                commission   = commission,
                comm_asset   = comm_asset,
                is_maker     = is_maker,
                realized_pnl = realized_pnl,
            )
        else:
            await _emit("order_filled", {
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
        log.error("_handle_order_update error: %s", e)


def _exit_reason(order_type: str, order_id: str, trade_sl: str, trade_tp: str) -> str:
    ot = order_type.upper()
    if "STOP" in ot:
        return "sl_hit"
    if ot == "LIMIT":
        return "tp_hit" if trade_tp and str(order_id) == str(trade_tp) else "tp_hit"
    if ot == "MARKET":
        return "manual_close"
    if "LIQUIDATION" in ot:
        return "liquidated"
    return "exchange_closed"


async def _handle_position_closed(
    coin:         str,
    exit_price:   float,
    order_id:     str,
    order_type:   str,
    commission:   float = 0.0,
    comm_asset:   str   = "USDT",
    is_maker:     bool  = False,
    realized_pnl: float = 0.0,
) -> None:
    try:
        from database import get_session, Trade as TradeModel, Signal as SignalModel
        from trade.monitor import invalidate_position_cache
        from trade.health_monitor import clear_health_state
        from trade.executor import _calc_pnl, _mark_closed

        with get_session() as db:
            trade = db.query(TradeModel).filter(
                TradeModel.is_active == True,
            ).filter(
                (TradeModel.sl_order_id   == order_id) |
                (TradeModel.tp1_order_id  == order_id) |
                (TradeModel.entry_order_id== order_id) |
                (TradeModel.coin          == coin)
            ).first()

            if not trade:
                log.debug("No active trade for %s order:%s", coin, order_id)
                return

            trade_id      = trade.id
            direction     = trade.direction
            entry         = float(trade.entry_price or 0)
            margin        = float(trade.margin_used or 0)
            leverage      = int(trade.leverage or 1)
            entry_fee     = float(trade.entry_commission or 0)
            sl_oid        = str(trade.sl_order_id  or "")
            tp_oid        = str(trade.tp1_order_id or "")

        reason       = _exit_reason(order_type, order_id, sl_oid, tp_oid)
        total_fee    = round(entry_fee + commission, 8)

        net_pnl = (
            round(realized_pnl - commission, 8) if realized_pnl != 0
            else _calc_pnl(
                direction  = direction,
                entry      = entry,
                exit_price = exit_price,
                margin     = margin,
                leverage   = leverage,
                commission = total_fee,
            )
        )

        slippage_exit = 0.0
        with get_session() as db:
            trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if trade:
                if reason == "tp_hit" and trade.tp1_price:
                    slippage_exit = abs(exit_price - float(trade.tp1_price)) / float(trade.tp1_price) * 100
                elif reason == "sl_hit" and trade.sl_price:
                    slippage_exit = abs(exit_price - float(trade.sl_price)) / float(trade.sl_price) * 100

        _mark_closed(
            trade_id          = trade_id,
            exit_price        = exit_price,
            pnl               = net_pnl,
            reason            = reason,
            exit_commission   = commission,
            exit_role         = "maker" if is_maker else "taker",
            total_commission  = total_fee,
            realized_pnl      = realized_pnl,
            slippage_exit_pct = slippage_exit,
        )

        invalidate_position_cache()
        clear_health_state(coin)

        emoji   = "✅" if net_pnl >= 0 else "❌"
        pnl_str = f"+${net_pnl:.4f}" if net_pnl >= 0 else f"-${abs(net_pnl):.4f}"

        from alerts.telegram import send
        await send(
            f"{emoji} *{coin} {direction} Closed*\n\n"
            f"Reason:  `{reason}`\n"
            f"Exit:    `${exit_price:.6f}`\n"
            f"PnL:     `{pnl_str}`\n"
            f"Fee:     `${total_fee:.4f}` ({'maker' if is_maker else 'taker'})\n"
            f"Realized:`${realized_pnl:.4f}` (exchange)"
        )

        await _emit("trade_closed", {
            "coin":       coin,
            "direction":  direction,
            "exit_price": exit_price,
            "net_pnl":    net_pnl,
            "commission": total_fee,
            "reason":     reason,
        })

        from events import emit
        asyncio.create_task(emit("trade_closed", {
            "coin":      coin,
            "direction": direction,
            "pnl":       net_pnl,
            "reason":    reason,
        }))

        log.info(
            "Position closed via WS: %s %s exit:%.6f pnl:%.4f fee:$%.6f reason:%s",
            coin, direction, exit_price, net_pnl, total_fee, reason,
        )

    except Exception as e:
        log.error("_handle_position_closed %s: %s", coin, e, exc_info=True)


async def _handle_account_update(data: dict) -> None:
    try:
        account = data.get("a", {})
        await _emit("account_update", {
            "balances":  account.get("B", []),
            "positions": account.get("P", []),
        })
    except Exception as e:
        log.error("_handle_account_update error: %s", e)


async def _listen_key_refresh_loop() -> None:
    while True:
        await asyncio.sleep(1200)
        try:
            if not await refresh_listen_key():
                log.warning("Listen key refresh failed")
        except Exception as e:
            log.error("Listen key refresh loop error: %s", e)


async def start_ws() -> None:
    global _ws_task, _user_ws_task, _listen_key_task
    if _ws_task and not _ws_task.done():
        return
    _ws_task         = asyncio.create_task(_mark_price_stream())
    _user_ws_task    = asyncio.create_task(_user_data_stream())
    _listen_key_task = asyncio.create_task(_listen_key_refresh_loop())
    log.info("Binance WebSocket streams started")


async def stop_ws() -> None:
    global _ws_task, _user_ws_task, _listen_key_task, _ws_connected, _user_ws_connected
    for task in (_ws_task, _user_ws_task, _listen_key_task):
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    _ws_task = _user_ws_task = _listen_key_task = None
    _ws_connected = _user_ws_connected = False
    try:
        await invalidate_listen_key()
    except Exception:
        pass
    log.info("Binance WebSocket streams stopped")