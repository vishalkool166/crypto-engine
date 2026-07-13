import asyncio
import logging
import time
from datetime import datetime, timezone
from database import get_session, Trade as TradeModel
from config import cfg
from trade.ws import get_mark_price

log = logging.getLogger(__name__)

SE = cfg.SCALP_ENGINE


def _get_open_scalp_trades() -> list:
    try:
        with get_session() as db:
            trades = db.query(TradeModel).filter(
                TradeModel.is_active == True
            ).all()
            return [{
                "id":           t.id,
                "coin":         t.coin,
                "direction":    t.direction,
                "entry_price":  float(t.entry_price  or 0),
                "sl_price":     float(t.sl_price     or 0),
                "tp1_price":    float(t.tp1_price     or 0),
                "tp2_price":    float(t.tp2_price     or 0),
                "margin_used":  float(t.margin_used   or 0),
                "leverage":     int(t.leverage        or 1),
                "tp1_hit":      bool(t.tp1_hit),
                "opened_at":    t.opened_at,
                "tp1_hit_at":   getattr(t, "tp1_hit_at", None),
            } for t in trades]
    except Exception as e:
        log.error("_get_open_scalp_trades: %s", e)
        return []


def _hours_since(dt) -> float:
    if not dt:
        return 0.0
    try:
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)
    except Exception:
        return 0.0


def _was_opened_during_asia(opened_at) -> bool:
    try:
        if not opened_at:
            return False
        if isinstance(opened_at, str):
            opened_at = datetime.fromisoformat(opened_at)
        if opened_at.tzinfo is None:
            opened_at = opened_at.replace(tzinfo=timezone.utc)
        return 0 <= opened_at.hour < 8
    except Exception:
        return False


def _is_asia_session() -> bool:
    return 0 <= datetime.now(timezone.utc).hour < 8


async def _partial_close(trade: dict, reason: str) -> bool:
    try:
        from trade.exchange import (
            get_positions, place_order, get_symbol_precision,
            cancel_all_orders, cancel_all_algo_orders
        )
        from trade.executor import _round_step, _mark_closed

        coin     = trade["coin"]
        symbol   = f"{coin}USDT"
        is_short = trade["direction"] == "SHORT"
        margin   = trade["margin_used"]
        leverage = trade["leverage"]

        positions = await get_positions()
        position  = next(
            (p for p in positions
             if p.get("symbol") == symbol and float(p.get("positionAmt", 0)) != 0),
            None
        )

        if not position:
            log.warning("_partial_close: no position found for %s", coin)
            return False

        total_qty  = abs(float(position.get("positionAmt", 0)))
        close_qty  = total_qty * SE["tp1_close_pct"]
        prec       = await get_symbol_precision(symbol)
        close_qty  = _round_step(close_qty, prec["step_size"])
        close_side = "BUY" if is_short else "SELL"

        if close_qty <= 0:
            return False

        order      = await place_order(
            symbol      = symbol,
            side        = close_side,
            order_type  = "MARKET",
            quantity    = close_qty,
            reduce_only = True,
        )

        exit_price = get_mark_price(coin) or trade["entry_price"]

        entry       = trade["entry_price"]
        ratio       = (entry - exit_price) / entry if is_short else (exit_price - entry) / entry
        partial_pnl = round(ratio * (close_qty * exit_price), 4)

        with get_session() as db:
            t = db.query(TradeModel).filter(TradeModel.id == trade["id"]).first()
            if t:
                t.tp1_hit     = True
                t.partial_pnl = partial_pnl
                t.sl_price    = entry
                db.commit()

        await _update_sl_to_breakeven(coin, symbol, entry, is_short, prec)

        from alerts.telegram import send
        await send(
            f"🎯 *{coin} TP1 Hit — Partial Close*\n\n"
            f"Closed:      `{SE['tp1_close_pct']*100:.0f}%` at `${exit_price:.6f}`\n"
            f"Partial PnL: `${partial_pnl:.4f}`\n"
            f"SL moved to breakeven: `${entry:.6f}`\n"
            f"Remaining `{SE['tp2_close_pct']*100:.0f}%` running to TP2"
        )

        log.info(
            "Partial close: %s %.0f%% at %.6f pnl:%.4f",
            coin, SE["tp1_close_pct"] * 100, exit_price, partial_pnl
        )
        return True

    except Exception as e:
        log.error("_partial_close %s: %s", trade["coin"], e, exc_info=True)
        return False


async def _update_sl_to_breakeven(
    coin:     str,
    symbol:   str,
    entry:    float,
    is_short: bool,
    prec:     dict,
) -> None:
    try:
        from trade.exchange import cancel_all_orders, cancel_all_algo_orders
        from trade.executor import _round_tick, move_sl_to_breakeven

        await cancel_all_orders(symbol)
        await cancel_all_algo_orders(symbol)
        await asyncio.sleep(1.0)

        atr_15m = entry * 0.005
        sl_side = "BUY" if not is_short else "SELL"

        await move_sl_to_breakeven(
            symbol          = symbol,
            side            = sl_side,
            entry_price     = entry,
            atr_15m         = atr_15m,
            price_precision = prec["price_precision"],
            tick_size       = prec["tick_size"],
            is_long         = not is_short,
        )

    except Exception as e:
        log.error("_update_sl_to_breakeven %s: %s", coin, e)


async def _time_stop_close(trade: dict, reason: str) -> None:
    try:
        with get_session() as db:
            t = db.query(TradeModel).filter(
                TradeModel.id        == trade["id"],
                TradeModel.is_active == True
            ).first()
            if not t:
                log.info("_time_stop_close: trade %s already closed", trade["id"])
                return

        from trade.executor import close_position
        await close_position(
            coin      = trade["coin"],
            direction = trade["direction"],
            trade_id  = trade["id"],
            reason    = reason,
        )
        from engines.state import set_idle, set_cooldown
        if reason == "time_stop_loss":
            set_cooldown(trade["coin"])
        else:
            set_idle(trade["coin"])
    except Exception as e:
        log.error("_time_stop_close %s: %s", trade["coin"], e)


async def run_cycle() -> None:
    trades = _get_open_scalp_trades()
    if not trades:
        return

    for trade in trades:
        coin       = trade["coin"]
        entry      = trade["entry_price"]
        is_short   = trade["direction"] == "SHORT"
        tp1_hit    = trade["tp1_hit"]
        opened_at  = trade["opened_at"]
        tp1_hit_at = trade["tp1_hit_at"]
        live_price = get_mark_price(coin) or entry

        move_pct = (
            (entry - live_price) / entry
            if is_short
            else (live_price - entry) / entry
        )

        if tp1_hit:
            hours_since_tp1 = _hours_since(tp1_hit_at)
            if hours_since_tp1 >= SE["time_stop_after_tp1_hours"]:
                log.info("Time stop after TP1: %s", coin)
                await _time_stop_close(trade, "time_stop_after_tp1")
            continue

        hours_open = _hours_since(opened_at)

        if SE["close_before_asia"] and _is_asia_session():
            opened_during_asia = _was_opened_during_asia(opened_at)
            if not opened_during_asia and move_pct <= 0:
                log.info(
                    "Close before Asia: %s move:%.3f%%",
                    coin, move_pct * 100
                )
                reason = "close_before_asia"
                await _time_stop_close(trade, reason)
                continue

        if hours_open >= SE["time_stop_hours"]:
            if move_pct > 0.002:
                reason = "time_stop_profit"
            elif abs(move_pct) <= 0.002:
                reason = "time_stop_breakeven"
            else:
                sl_dist = abs(entry - trade["sl_price"]) / entry if trade["sl_price"] else 0.02
                if abs(move_pct) < sl_dist * 0.7:
                    reason = "time_stop_loss"
                else:
                    continue

            log.info(
                "Time stop: %s reason:%s move:%.3f%%",
                coin, reason, move_pct * 100
            )
            await _time_stop_close(trade, reason)


async def handle_tp1_hit(coin: str) -> None:
    trades = _get_open_scalp_trades()
    trade  = next((t for t in trades if t["coin"] == coin and not t["tp1_hit"]), None)
    if not trade:
        return
    await _partial_close(trade, "tp1_hit")