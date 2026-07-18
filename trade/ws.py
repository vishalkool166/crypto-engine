import asyncio
import json
import logging
import time
import websockets
from datetime import datetime, timezone
from trade.exchange import (
    get_listen_key, refresh_listen_key,
    invalidate_listen_key, get_ws_base_url,
    get_positions, get_symbol_precision,
)
from config import cfg

log = logging.getLogger(__name__)

_mark_prices:           dict                = {}
_ws_task:               asyncio.Task | None = None
_user_ws_task:          asyncio.Task | None = None
_kline_ws_task:         asyncio.Task | None = None
_ticker_ws_task:        asyncio.Task | None = None
_listen_key_task:       asyncio.Task | None = None
_ws_connected:          bool                = False
_user_ws_connected:     bool                = False
_kline_ws_connected:    bool                = False
_ticker_ws_connected:   bool                = False
_pending_commissions:   dict                = {}
_trade_event_callbacks: list                = []
_kline_callbacks:       list                = []

_binance_account: dict = {
    "wallet_balance":       0.0,
    "available_balance":    0.0,
    "total_unrealized_pnl": 0.0,
    "positions":            {},
    "updated_at":           time.time(),
}


def on_trade_event(callback) -> None:
    if callback not in _trade_event_callbacks:
        _trade_event_callbacks.append(callback)


def on_kline_closed(callback) -> None:
    if callback not in _kline_callbacks:
        _kline_callbacks.append(callback)


def get_mark_price(coin: str) -> float:
    return _mark_prices.get(f"{coin}USDT", 0.0)


def get_all_mark_prices() -> dict:
    return dict(_mark_prices)


def get_pending_commission(order_id: str) -> dict | None:
    return _pending_commissions.get(str(order_id))


def clear_pending_commission(order_id: str) -> None:
    _pending_commissions.pop(str(order_id), None)


def get_binance_account() -> dict:
    return dict(_binance_account)


def get_binance_position(coin: str) -> dict | None:
    return _binance_account["positions"].get(f"{coin}USDT")


def get_binance_unrealized_pnl(coin: str) -> float | None:
    pos = get_binance_position(coin)
    if pos:
        return float(pos.get("unrealizedProfit", 0) or 0)
    return None


def get_ws_status() -> dict:
    return {
        "mark_price_connected": _ws_connected,
        "user_data_connected":  _user_ws_connected,
        "kline_ws_connected":   _kline_ws_connected,
        "ticker_ws_connected":  _ticker_ws_connected,
        "prices_cached":        len(_mark_prices),
        "mode":                 cfg.TRADING_MODE,
        "binance_account_age":  round(time.time() - _binance_account["updated_at"], 0),
    }


async def _emit(event_type: str, data: dict) -> None:
    for cb in _trade_event_callbacks:
        try:
            await cb(event_type, data)
        except Exception as e:
            log.error("Trade event callback error: %s", e)


async def _emit_kline(coin: str, kline: dict) -> None:
    for cb in _kline_callbacks:
        try:
            await cb(coin, kline)
        except Exception as e:
            log.error("Kline callback error: %s", e)


async def _mark_price_stream() -> None:
    global _ws_connected
    while True:
        try:
            url = f"{get_ws_base_url()}/ws/!markPrice@arr@1s"
            async with websockets.connect(url, ping_interval=20, ping_timeout=10, open_timeout=15) as ws:
                _ws_connected = True
                log.info("Mark price WS connected")
                async for message in ws:
                    try:
                        data  = json.loads(message)
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
            log.warning("Mark price WS closed: %s", e)
        except Exception as e:
            _ws_connected = False
            log.warning("Mark price WS error: %s", e)
        await asyncio.sleep(5)


async def _ticker_stream() -> None:
    global _ticker_ws_connected
    while True:
        try:
            url = f"{get_ws_base_url()}/ws/!miniTicker@arr"
            async with websockets.connect(url, ping_interval=20, ping_timeout=10, open_timeout=15) as ws:
                _ticker_ws_connected = True
                log.info("Ticker WS connected")
                async for message in ws:
                    try:
                        data  = json.loads(message)
                        items = data if isinstance(data, list) else [data]
                        r = None
                        try:
                            from redis_client import get_redis
                            r = get_redis()
                        except Exception:
                            pass
                        for item in items:
                            symbol = item.get("s", "")
                            if not symbol.endswith("USDT"):
                                continue
                            close_price = float(item.get("c", 0))
                            open_price  = float(item.get("o", 0))
                            change_pct  = (
                                (close_price - open_price) / open_price * 100
                                if open_price > 0 else 0.0
                            )
                            if r:
                                try:
                                    r.setex(
                                        f"ticker:{symbol}",
                                        120,
                                        json.dumps({
                                            "last":       close_price,
                                            "percentage": round(change_pct, 4),
                                            "open":       open_price,
                                        })
                                    )
                                except Exception:
                                    pass
                    except Exception:
                        pass
        except websockets.exceptions.ConnectionClosedError as e:
            _ticker_ws_connected = False
            log.warning("Ticker WS closed: %s", e)
        except Exception as e:
            _ticker_ws_connected = False
            log.warning("Ticker WS error: %s", e)
        await asyncio.sleep(5)


async def _kline_stream() -> None:
    global _kline_ws_connected
    while True:
        try:
            coins = cfg.COINS
            if not coins:
                await asyncio.sleep(10)
                continue

            tf      = cfg.SCALP_ENGINE["kline_trigger_tf"]
            streams = "/".join(f"{c.lower()}usdt@kline_{tf}" for c in coins)
            url     = f"{get_ws_base_url()}/stream?streams={streams}"

            async with websockets.connect(url, ping_interval=20, ping_timeout=10, open_timeout=15) as ws:
                _kline_ws_connected = True
                log.info("Kline WS connected — %s coins", len(coins))
                async for message in ws:
                    try:
                        data  = json.loads(message)
                        kline = data.get("data", {}).get("k", {})
                        if not kline or not kline.get("x"):
                            continue
                        symbol = kline.get("s", "")
                        coin   = symbol.replace("USDT", "")
                        if coin not in coins:
                            continue
                        parsed = {
                            "coin":      coin,
                            "tf":        tf,
                            "open":      float(kline["o"]),
                            "high":      float(kline["h"]),
                            "low":       float(kline["l"]),
                            "close":     float(kline["c"]),
                            "volume":    float(kline["v"]),
                            "timestamp": int(kline["t"]),
                            "closed":    True,
                        }
                        await _emit_kline(coin, parsed)
                    except Exception as e:
                        log.error("Kline parse error: %s", e)

        except websockets.exceptions.ConnectionClosedError as e:
            _kline_ws_connected = False
            log.warning("Kline WS closed: %s", e)
        except Exception as e:
            _kline_ws_connected = False
            log.warning("Kline WS error: %s", e)
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
            async with websockets.connect(url, ping_interval=20, ping_timeout=10, open_timeout=15) as ws:
                _user_ws_connected = True
                log.info("User data WS connected")
                async for message in ws:
                    try:
                        data = json.loads(message)
                        et   = data.get("e", "")
                        if et == "ORDER_TRADE_UPDATE":
                            await _handle_order_update(data)
                        elif et == "ACCOUNT_UPDATE":
                            await _handle_account_update(data)
                        elif et == "listenKeyExpired":
                            _user_ws_connected = False
                            break
                    except Exception as e:
                        log.error("User data WS parse error: %s", e)
        except websockets.exceptions.ConnectionClosedError as e:
            _user_ws_connected = False
            log.warning("User data WS closed: %s", e)
        except Exception as e:
            _user_ws_connected = False
            log.warning("User data WS error: %s", e)
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
            "raw":              order,
        }

        if reduce_only or close_pos:
            await _handle_reduce_order_filled(
                coin         = coin,
                symbol       = symbol,
                order_id     = order_id,
                order_type   = order_type,
                exit_price   = avg_price,
                filled_qty   = filled_qty,
                commission   = commission,
                comm_asset   = comm_asset,
                is_maker     = is_maker,
                realized_pnl = realized_pnl,
                raw_order    = order,
            )
        else:
            await _handle_entry_order_filled(
                coin         = coin,
                symbol       = symbol,
                order_id     = order_id,
                fill_price   = avg_price,
                filled_qty   = filled_qty,
                commission   = commission,
                comm_asset   = comm_asset,
                is_maker     = is_maker,
                realized_pnl = realized_pnl,
                raw_order    = order,
                side         = side,
            )

    except Exception as e:
        log.error("_handle_order_update: %s", e)


async def _handle_entry_order_filled(
    coin:         str,
    symbol:       str,
    order_id:     str,
    fill_price:   float,
    filled_qty:   float,
    commission:   float,
    comm_asset:   str,
    is_maker:     bool,
    realized_pnl: float,
    raw_order:    dict,
    side:         str,
) -> None:
    try:
        from database import SessionLocal, Trade as TradeModel

        with SessionLocal() as db:
            trade = db.query(TradeModel).filter(
                TradeModel.entry_order_id == order_id,
                TradeModel.is_active      == True,
            ).first()

            if not trade:
                trade = db.query(TradeModel).filter(
                    TradeModel.coin      == coin,
                    TradeModel.is_active == True,
                ).order_by(TradeModel.opened_at.desc()).first()

            if not trade:
                return

            trade_id  = trade.id
            direction = trade.direction

        asyncio.create_task(
            _sync_entry_async(
                trade_id     = trade_id,
                coin         = coin,
                direction    = direction,
                order_id     = order_id,
                fill_price   = fill_price,
                filled_qty   = filled_qty,
                commission   = commission,
                comm_asset   = comm_asset,
                is_maker     = is_maker,
                realized_pnl = realized_pnl,
                raw_order    = raw_order,
            )
        )

        await _emit("order_filled", {
            "coin":         coin,
            "order_id":     order_id,
            "side":         side,
            "price":        fill_price,
            "quantity":     filled_qty,
            "commission":   commission,
            "role":         "maker" if is_maker else "taker",
            "realized_pnl": realized_pnl,
        })

    except Exception as e:
        log.error("_handle_entry_order_filled %s: %s", coin, e)


async def _sync_entry_async(
    trade_id:     int,
    coin:         str,
    direction:    str,
    order_id:     str,
    fill_price:   float,
    filled_qty:   float,
    commission:   float,
    comm_asset:   str,
    is_maker:     bool,
    realized_pnl: float,
    raw_order:    dict,
) -> None:
    try:
        await asyncio.sleep(3.0)
        from trade.binance_sync import sync_trade_open
        await sync_trade_open(
            trade_id         = trade_id,
            coin             = coin,
            direction        = direction,
            entry_order_id   = order_id,
            fill_price       = fill_price,
            filled_qty       = filled_qty,
            commission       = commission,
            commission_asset = comm_asset,
            entry_role       = "maker" if is_maker else "taker",
            realized_pnl     = realized_pnl,
            raw_order_json   = raw_order,
        )
    except Exception as e:
        log.error("_sync_entry_async trade_id=%s: %s", trade_id, e)


async def _handle_reduce_order_filled(
    coin:         str,
    symbol:       str,
    order_id:     str,
    order_type:   str,
    exit_price:   float,
    filled_qty:   float,
    commission:   float = 0.0,
    comm_asset:   str   = "USDT",
    is_maker:     bool  = False,
    realized_pnl: float = 0.0,
    raw_order:    dict  = None,
) -> None:
    try:
        from database import get_session, Trade as TradeModel, Signal as SignalModel
        from trade.monitor import invalidate_position_cache
        from trade.health_monitor import clear_health_state
        from trade.executor import _calc_pnl, _mark_closed, CLOSE_REASONS
        from engines.state import set_cooldown, set_idle

        with get_session() as db:
            trade = db.query(TradeModel).filter(
                TradeModel.is_active == True,
            ).filter(
                (TradeModel.sl_order_id    == order_id) |
                (TradeModel.tp1_order_id   == order_id) |
                (TradeModel.entry_order_id == order_id) |
                (TradeModel.coin           == coin)
            ).first()

            if not trade:
                log.debug("No active trade for %s order:%s", coin, order_id)
                return

            trade_id   = trade.id
            direction  = trade.direction
            entry      = float(trade.entry_price   or 0)
            margin     = float(trade.margin_used   or 0)
            leverage   = int(trade.leverage        or 1)
            entry_fee  = float(trade.entry_commission or 0)
            sl_oid     = str(trade.sl_order_id     or "")
            tp1_oid    = str(trade.tp1_order_id    or "")
            is_long    = direction == "LONG"

        reason    = _exit_reason(order_type, order_id, sl_oid, tp1_oid, entry, exit_price, is_long)
        total_fee = round(entry_fee + commission, 8)

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
                if reason == "tp1_hit" and trade.tp1_price:
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

        asyncio.create_task(
            _sync_close_async(
                trade_id     = trade_id,
                coin         = coin,
                direction    = direction,
                order_id     = order_id,
                exit_price   = exit_price,
                exit_qty     = filled_qty,
                commission   = commission,
                exit_role    = "maker" if is_maker else "taker",
                realized_pnl = realized_pnl,
                raw_order    = raw_order or {},
            )
        )

        try:
            from ml.outcome_recorder import record
            asyncio.create_task(record(trade_id))
        except Exception as _oe:
            log.error("outcome_recorder failed trade_id=%s: %s", trade_id, _oe)

        try:
            from trade.thesis_tracker import remove_thesis
            remove_thesis(trade_id)
        except Exception:
            pass

        if reason == "sl_hit":
            set_cooldown(coin)
        else:
            set_idle(coin)

        pnl_str      = f"+${net_pnl:.4f}" if net_pnl >= 0 else f"-${abs(net_pnl):.4f}"
        emoji        = "✅" if net_pnl >= 0 else "❌"
        reason_label = CLOSE_REASONS.get(reason, reason)

        from alerts.telegram import send
        await send(
            f"{emoji} *{coin} {direction} Closed*\n\n"
            f"Reason:  `{reason_label}`\n"
            f"Exit:    `${exit_price:.6f}`\n"
            f"PnL:     `{pnl_str}`\n"
            f"Fee:     `${total_fee:.4f}`"
        )

        await _emit("trade_closed", {
            "coin":       coin,
            "direction":  direction,
            "exit_price": exit_price,
            "net_pnl":    net_pnl,
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
            "Position closed: %s %s exit:%.6f pnl:%.4f fee:$%.6f reason:%s",
            coin, direction, exit_price, net_pnl, total_fee, reason,
        )

    except Exception as e:
        log.error("_handle_reduce_order_filled %s: %s", coin, e, exc_info=True)


async def _sync_close_async(
    trade_id:     int,
    coin:         str,
    direction:    str,
    order_id:     str,
    exit_price:   float,
    exit_qty:     float,
    commission:   float,
    exit_role:    str,
    realized_pnl: float,
    raw_order:    dict,
) -> None:
    try:
        await asyncio.sleep(2.0)
        from trade.binance_sync import sync_trade_close
        await sync_trade_close(
            trade_id        = trade_id,
            coin            = coin,
            direction       = direction,
            exit_order_id   = order_id,
            exit_price      = exit_price,
            exit_qty        = exit_qty,
            exit_commission = commission,
            exit_role       = exit_role,
            realized_pnl    = realized_pnl,
            raw_order_json  = raw_order,
        )
    except Exception as e:
        log.error("_sync_close_async trade_id=%s: %s", trade_id, e)


def _exit_reason(
    order_type: str,
    order_id:   str,
    sl_oid:     str,
    tp1_oid:    str,
    entry:      float = 0.0,
    exit_price: float = 0.0,
    is_long:    bool  = True,
) -> str:
    if order_id == tp1_oid:
        return "tp1_hit"
    if order_id == sl_oid:
        return "sl_hit"

    ot = order_type.upper()

    if "STOP"        in ot: return "sl_hit"
    if "TAKE_PROFIT" in ot: return "tp1_hit"
    if "LIQUIDATION" in ot: return "liquidated"

    if entry > 0 and exit_price > 0:
        if is_long:
            return "tp1_hit" if exit_price > entry else "sl_hit"
        else:
            return "tp1_hit" if exit_price < entry else "sl_hit"

    return "exchange_closed"


async def _handle_account_update(data: dict) -> None:
    try:
        account  = data.get("a", {})
        balances = account.get("B", [])
        positions= account.get("P", [])

        for b in balances:
            if b.get("a") == "USDT":
                _binance_account["wallet_balance"]    = float(b.get("wb", 0) or 0)
                _binance_account["available_balance"] = float(b.get("cw", 0) or 0)
                break

        total_unrealized = 0.0
        for p in positions:
            symbol = p.get("s", "")
            if not symbol:
                continue
            unrealized = float(p.get("up", 0) or 0)
            total_unrealized += unrealized
            _binance_account["positions"][symbol] = {
                "symbol":           symbol,
                "positionAmt":      float(p.get("pa", 0) or 0),
                "entryPrice":       float(p.get("ep", 0) or 0),
                "unrealizedProfit": unrealized,
                "marginType":       p.get("mt", "isolated"),
                "isolatedMargin":   float(p.get("iw", 0) or 0),
                "updated_at":       time.time(),
            }

        _binance_account["total_unrealized_pnl"] = total_unrealized
        _binance_account["updated_at"]           = time.time()

        try:
            from redis_client import get_redis
            r = get_redis()
            if r:
                r.setex("binance:account", 60, json.dumps({
                    "wallet_balance":       _binance_account["wallet_balance"],
                    "available_balance":    _binance_account["available_balance"],
                    "total_unrealized_pnl": total_unrealized,
                    "updated_at":           _binance_account["updated_at"],
                }))
                for symbol, pos_data in _binance_account["positions"].items():
                    r.setex(f"binance:position:{symbol}", 60, json.dumps(pos_data))
        except Exception:
            pass

        await _emit("account_update", {
            "balances":             balances,
            "positions":            positions,
            "wallet_balance":       _binance_account["wallet_balance"],
            "total_unrealized_pnl": total_unrealized,
        })

    except Exception as e:
        log.error("_handle_account_update: %s", e)


async def _listen_key_refresh_loop() -> None:
    while True:
        await asyncio.sleep(1200)
        try:
            if not await refresh_listen_key():
                log.warning("Listen key refresh failed")
        except Exception as e:
            log.error("Listen key refresh error: %s", e)


async def start_ws() -> None:
    global _ws_task, _user_ws_task, _kline_ws_task, _ticker_ws_task, _listen_key_task
    if _ws_task and not _ws_task.done():
        return
    _ws_task         = asyncio.create_task(_mark_price_stream())
    _ticker_ws_task  = asyncio.create_task(_ticker_stream())
    _user_ws_task    = asyncio.create_task(_user_data_stream())
    _kline_ws_task   = asyncio.create_task(_kline_stream())
    _listen_key_task = asyncio.create_task(_listen_key_refresh_loop())
    log.info("WebSocket streams started")


async def stop_ws() -> None:
    global _ws_task, _user_ws_task, _kline_ws_task, _ticker_ws_task, _listen_key_task
    global _ws_connected, _user_ws_connected, _kline_ws_connected, _ticker_ws_connected

    for task in (_ws_task, _user_ws_task, _kline_ws_task, _ticker_ws_task, _listen_key_task):
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    _ws_task = _user_ws_task = _kline_ws_task = _ticker_ws_task = _listen_key_task = None
    _ws_connected = _user_ws_connected = _kline_ws_connected = _ticker_ws_connected = False

    try:
        await invalidate_listen_key()
    except Exception:
        pass

    log.info("WebSocket streams stopped")