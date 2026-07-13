import asyncio
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


async def run_exit_cycle(trade: dict) -> None:
    trade_id  = trade["id"]
    coin      = trade["coin"]
    direction = trade["direction"]
    grade     = trade.get("grade", "A")

    try:
        from trade.thesis_tracker import get_thesis, evaluate
        from trade.executor import close_position
        from trade.exchange import get_symbol_precision
        from trade.ws import get_mark_price
        from engines.state import set_cooldown, set_idle

        thesis = get_thesis(trade_id)
        if not thesis:
            return

        thesis = await evaluate(trade_id, trade)
        if not thesis:
            return

        action  = thesis.action
        reason  = thesis.action_reason
        is_long = direction == "LONG"

        if action == "exit":
            await _execute_exit(
                trade_id  = trade_id,
                coin      = coin,
                direction = direction,
                reason    = _map_exit_reason(thesis),
                thesis    = thesis,
            )
            return

        if action in ("tighten", "prepare_exit"):
            await _tighten_sl(
                trade    = trade,
                thesis   = thesis,
                is_long  = is_long,
            )
            return

        if action == "monitor":
            await _soft_tighten_sl(
                trade   = trade,
                thesis  = thesis,
                is_long = is_long,
            )
            return

    except Exception as e:
        log.error("run_exit_cycle trade_id=%s: %s", trade_id, e)


async def _execute_exit(
    trade_id:  int,
    coin:      str,
    direction: str,
    reason:    str,
    thesis,
) -> None:
    try:
        from trade.executor import close_position
        from trade.thesis_tracker import remove_thesis
        from database import get_session, Trade as TradeModel
        import json

        with get_session() as db:
            t = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if not t or not t.is_active:
                remove_thesis(trade_id)
                return

            t.thesis_strength_at_close  = thesis.thesis_strength
            t.thesis_pillars_at_close   = _pillars_json(thesis)
            t.thesis_exit_reason        = thesis.action_reason
            t.captured_move_pct_at_exit = thesis.captured_move_pct
            t.expected_move_pct         = thesis.expected_move_pct
            t.velocity_at_close         = thesis.velocity

        result = await close_position(
            coin      = coin,
            direction = direction,
            trade_id  = trade_id,
            reason    = reason,
        )

        remove_thesis(trade_id)

        from engines.state import set_cooldown, set_idle
        if reason == "sl_hit":
            set_cooldown(coin)
        else:
            set_idle(coin)

        log.info(
            "Exit executed: %s trade_id:%s reason:%s strength:%.2f captured:%.1f%%",
            coin, trade_id, reason,
            thesis.thesis_strength,
            thesis.captured_move_pct,
        )

    except Exception as e:
        log.error("_execute_exit trade_id=%s: %s", trade_id, e)


async def _tighten_sl(trade: dict, thesis, is_long: bool) -> None:
    try:
        coin      = trade["coin"]
        trade_id  = trade["id"]
        entry     = float(trade.get("entry_price") or 0)
        sl        = float(trade.get("sl_price")    or 0)
        move_pct  = thesis.move_pct
        strength  = thesis.thesis_strength

        if not entry or not sl:
            return

        from trade.ws import get_mark_price
        live_price = get_mark_price(coin) or entry

        symbol = f"{coin}USDT"

        from trade.exchange import get_symbol_precision
        prec      = await get_symbol_precision(symbol)
        tick_size = prec["tick_size"]

        from trade.executor import move_sl_to_breakeven, _round_tick

        if move_pct > 0:
            new_sl = await move_sl_to_breakeven(
                symbol          = symbol,
                side            = "BUY" if not is_long else "SELL",
                entry_price     = entry,
                atr_15m         = entry * 0.003,
                price_precision = prec["price_precision"],
                tick_size       = tick_size,
                is_long         = is_long,
            )
            if new_sl:
                from database import get_session, Trade as TradeModel
                with get_session() as db:
                    t = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
                    if t:
                        t.sl_price    = entry
                        t.sl_order_id = new_sl
                log.info(
                    "SL tightened to BE: %s trade_id:%s strength:%.2f",
                    coin, trade_id, strength
                )
        else:
            tighten_pct = 0.30 if strength < 0.40 else 0.20
            sl_dist     = abs(entry - sl)
            if is_long:
                new_sl_price = sl + sl_dist * tighten_pct
            else:
                new_sl_price = sl - sl_dist * tighten_pct

            if tick_size and tick_size > 0:
                new_sl_price = _round_tick(new_sl_price, tick_size)

            from trade.exchange import cancel_all_algo_orders, place_algo_order
            await cancel_all_algo_orders(symbol)
            await asyncio.sleep(0.5)

            sl_side = "BUY" if not is_long else "SELL"
            order   = await place_algo_order(
                symbol          = symbol,
                side            = sl_side,
                order_type      = "STOP_MARKET",
                trigger_price   = new_sl_price,
                price_precision = prec["price_precision"],
                close_position  = True,
            )
            algo_id = str(order.get("algoId", ""))
            if algo_id and algo_id != "0":
                from database import get_session, Trade as TradeModel
                with get_session() as db:
                    t = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
                    if t:
                        t.sl_price    = new_sl_price
                        t.sl_order_id = algo_id
                log.info(
                    "SL tightened: %s trade_id:%s %.6f→%.6f strength:%.2f",
                    coin, trade_id, sl, new_sl_price, strength
                )

    except Exception as e:
        log.error("_tighten_sl trade_id=%s: %s", trade["id"], e)


async def _soft_tighten_sl(trade: dict, thesis, is_long: bool) -> None:
    try:
        coin     = trade["coin"]
        trade_id = trade["id"]
        entry    = float(trade.get("entry_price") or 0)
        sl       = float(trade.get("sl_price")    or 0)

        if not entry or not sl:
            return

        symbol    = f"{coin}USDT"
        sl_dist   = abs(entry - sl)
        tighten   = sl_dist * 0.10

        from trade.executor import _round_tick
        from trade.exchange import get_symbol_precision, cancel_all_algo_orders, place_algo_order

        prec      = await get_symbol_precision(symbol)
        tick_size = prec["tick_size"]

        if is_long:
            new_sl_price = sl + tighten
        else:
            new_sl_price = sl - tighten

        if tick_size and tick_size > 0:
            new_sl_price = _round_tick(new_sl_price, tick_size)

        await cancel_all_algo_orders(symbol)
        await asyncio.sleep(0.5)

        sl_side = "BUY" if not is_long else "SELL"
        order   = await place_algo_order(
            symbol          = symbol,
            side            = sl_side,
            order_type      = "STOP_MARKET",
            trigger_price   = new_sl_price,
            price_precision = prec["price_precision"],
            close_position  = True,
        )
        algo_id = str(order.get("algoId", ""))
        if algo_id and algo_id != "0":
            from database import get_session, Trade as TradeModel
            with get_session() as db:
                t = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
                if t:
                    t.sl_price    = new_sl_price
                    t.sl_order_id = algo_id
            log.info(
                "SL soft tightened: %s trade_id:%s %.6f→%.6f",
                coin, trade_id, sl, new_sl_price
            )

    except Exception as e:
        log.error("_soft_tighten_sl trade_id=%s: %s", trade["id"], e)


def _map_exit_reason(thesis) -> str:
    action   = thesis.action
    strength = thesis.thesis_strength
    stalled  = thesis.velocity_stalled
    move_pct = thesis.move_pct
    captured = thesis.captured_move_pct
    hours    = thesis.hours_open

    from trade.thesis_tracker import GRADE_TIME_LIMITS
    time_limit = GRADE_TIME_LIMITS.get(thesis.grade, 8.0)

    if hours >= time_limit:
        if move_pct > 0.1:
            return "time_stop_profit"
        elif move_pct > -0.1:
            return "time_stop_breakeven"
        else:
            return "time_stop_loss"

    if strength < 0.20:
        return "thesis_invalidated"

    if stalled and captured >= 60:
        return "time_stop_profit"

    if stalled and move_pct > 0:
        return "time_stop_profit"

    return "thesis_degraded"


def _pillars_json(thesis) -> str:
    import json
    pillars = {}
    for name, pillar in thesis.pillars.items():
        pillars[name] = {
            "valid":  pillar.valid,
            "score":  round(pillar.score, 3),
            "reason": pillar.reason,
        }
    return json.dumps(pillars)


async def initialize_thesis_for_trade(trade: dict, signal_data: dict) -> None:
    try:
        from trade.thesis_tracker import create_thesis, get_thesis

        trade_id = trade["id"]

        if get_thesis(trade_id):
            return

        create_thesis(
            trade_id    = trade_id,
            coin        = trade["coin"],
            direction   = trade["direction"],
            grade       = trade.get("grade", "A"),
            entry_price = float(trade.get("entry_price") or 0),
            sl_price    = float(trade.get("sl_price")    or 0),
            tp1_price   = float(trade.get("tp1_price")   or 0),
            tp2_price   = float(trade.get("tp2_price")   or 0) or None,
            regime      = trade.get("regime_at_entry",  ""),
            session     = trade.get("session_at_entry", ""),
            signal_data = signal_data,
        )

    except Exception as e:
        log.error("initialize_thesis_for_trade trade_id=%s: %s", trade.get("id"), e)


async def load_signal_data_for_trade(trade_id: int, signal_id: int) -> dict:
    try:
        from database import SessionLocal, Signal as SignalModel
        with SessionLocal() as db:
            sig = db.query(SignalModel).filter(SignalModel.id == signal_id).first()
            if not sig:
                return {}
            return {
                "sweep_score":   float(sig.sweep_score  or 0),
                "zone_score":    float(sig.market_score or 0) / 100 if sig.market_score else 0,
                "trigger_score": float(sig.disp_score   or 0),
                "grade":         sig.grade or "A",
                "score":         float(sig.score        or 0),
            }
    except Exception as e:
        log.error("load_signal_data_for_trade: %s", e)
        return {}