import asyncio
import logging
from datetime import datetime, timezone
from database import get_session, Trade, Signal as SignalModel
from trade.state import state_manager, TradeState
from trade.risk import risk_guard, get_current_tier
from trade.orders import (
    set_leverage, place_market_order,
    place_sl_order, place_tp_order,
    cancel_order, get_order_status,
    get_current_price, close_position_market,
    calculate_quantity, _ensure_isolated_margin
)
from alerts.telegram import send
from alerts.utils import now_ist
from config import cfg

log = logging.getLogger(__name__)

TAKER_FEE = 0.0006
ENTRY_TOL = 0.003

_open_lock = asyncio.Lock()


class TradeManager:

    def __init__(self):
        self._last_db_update: dict[int, float] = {}

    async def on_price_update(self, coin: str, price: float):
        for trade_id, trade in list(state_manager.active_trades.items()):
            if trade.coin != coin:
                continue

            now = asyncio.get_running_loop().time()
            if now - self._last_db_update.get(trade_id, 0) > 10:
                try:
                    with get_session() as db:
                        t = db.query(Trade).filter(Trade.id == trade_id).first()
                        if t:
                            t.current_price = price
                except Exception as e:
                    log.error(f"Price update DB error: {e}")
                self._last_db_update[trade_id] = now

            await self._check_sl_tp(trade, price)

    async def _check_sl_tp(self, trade: Trade, current_price: float):
        trade_id = trade.id
        tp1_hit  = state_manager.is_tp1_hit_for(trade_id)

        def fresh():
            with get_session() as db:
                return db.query(Trade).filter(Trade.id == trade_id).first()

        if not tp1_hit:
            if trade.sl_order_id:
                sl_status = get_order_status(trade.coin, str(trade.sl_order_id))
                if sl_status and sl_status["status"] == "closed":
                    await self._close_trade(fresh(), current_price, "loss", "SL", 1)
                    return

            if trade.tp1_order_id:
                tp1_status = get_order_status(trade.coin, str(trade.tp1_order_id))
                if tp1_status and tp1_status["status"] == "closed":
                    await self._handle_tp1_hit(fresh(), current_price)
                    return
        else:
            if trade.sl_order_id:
                sl_status = get_order_status(trade.coin, str(trade.sl_order_id))
                if sl_status and sl_status["status"] == "closed":
                    await self._close_trade(fresh(), trade.entry_price, "win", "TP1 + BE", 2)
                    return

            if trade.tp2_order_id:
                tp2_status = get_order_status(trade.coin, str(trade.tp2_order_id))
                if tp2_status and tp2_status["status"] == "closed":
                    await self._close_trade(fresh(), current_price, "win", "TP2", 2)
                    return

    async def run_health_check_only(self):
        for trade_id, trade in list(state_manager.active_trades.items()):
            from trade.price_feed import price_feed
            current = price_feed.get_price(trade.coin) or get_current_price(trade.coin)
            with get_session() as db:
                t = db.query(Trade).filter(Trade.id == trade_id).first()
            if t:
                await self._run_health_check(t, current)

    async def sync_binance_positions(self):
        if cfg.PAPER_TRADING:
            return
        try:
            from trade.orders import exchange
            positions = exchange.fetch_positions()
            for pos in positions:
                contracts = float(pos.get("contracts", 0) or 0)
                if contracts <= 0:
                    continue

                symbol = pos.get("symbol", "")
                if "/" in symbol:
                    coin = symbol.split("/")[0]
                elif symbol.endswith("USDT"):
                    coin = symbol[:-4]
                else:
                    continue

                side      = pos.get("side", "")
                direction = "LONG" if side == "long" else "SHORT"
                entry     = float(pos.get("entryPrice", 0) or 0)
                tier      = get_current_tier()
                actual_leverage = int(float(pos.get("leverage", tier["leverage"]) or tier["leverage"]))
                size      = abs(float(pos.get("notional", 0) or contracts * entry))

                already_tracked = any(
                    t.coin == coin and t.direction == direction
                    for t in state_manager.active_trades.values()
                )
                if already_tracked:
                    continue

                log.info(f"[SYNC] Detected untracked Binance position: {coin} {direction} @ {entry}")

                import runtime_state as rs
                balance_now = rs.get_balance_cache().get("balance", cfg.CAPITAL)

                with get_session() as db:
                    existing = db.query(Trade).filter(
                        Trade.coin      == coin,
                        Trade.direction == direction,
                        Trade.is_active == True
                    ).first()

                    if existing:
                        state_manager.set_in_trade(existing)
                        log.info(f"[SYNC] Re-linked existing DB trade: {coin} {direction}")
                        continue

                    trade = Trade(
                        coin             = coin,
                        direction        = direction,
                        grade            = "M",
                        state            = TradeState.IN_TRADE,
                        is_active        = True,
                        entry_price      = entry,
                        sl_price         = None,
                        tp1_price        = None,
                        tp2_price        = None,
                        position_size    = size,
                        margin_used      = size / actual_leverage,
                        leverage         = actual_leverage,
                        risk_amt         = 0,
                        trade_date       = str(datetime.now(timezone.utc).date()),
                        balance_at_open  = balance_now,
                        tier_at_open     = tier["tier"],
                        notes            = "manual_import:binance_sync"
                    )
                    db.add(trade)
                    db.flush()
                    db.refresh(trade)

                state_manager.set_in_trade(trade)

                from trade.price_feed import price_feed
                await price_feed.start(coin)

                await send(
                    f"📥 *Manual Trade Detected*\n\n"
                    f"{'📈' if direction == 'LONG' else '📉'} *{coin}USDT {direction}*\n"
                    f"Entry: `{entry}`\n"
                    f"Size:  `${size:.2f}`\n\n"
                    f"⚠️ No SL/TP set — set levels with:\n"
                    f"`/setlevels {coin} <sl> <tp1> <tp2>`\n\n"
                    f"Example:\n"
                    f"`/setlevels {coin} 0.0950 0.0850 0.0800`"
                )

        except Exception as e:
            log.error(f"Binance position sync error: {e}")

    async def set_trade_levels(self, coin: str, sl: float, tp1: float, tp2: float) -> dict:
        trade = next(
            (t for t in state_manager.active_trades.values() if t.coin == coin),
            None
        )
        if not trade:
            return {"success": False, "reason": f"No active trade for {coin}"}

        with get_session() as db:
            t = db.query(Trade).filter(Trade.id == trade.id).first()
            if not t:
                return {"success": False, "reason": "Trade not found in DB"}
            t.sl_price  = sl
            t.tp1_price = tp1
            t.tp2_price = tp2
            trade.sl_price  = sl
            trade.tp1_price = tp1
            trade.tp2_price = tp2

        log.info(f"Levels set for {coin}: SL:{sl} TP1:{tp1} TP2:{tp2}")
        return {"success": True}

    async def open_trade(self, signal: dict, signal_id: int = None) -> dict:
        async with _open_lock:
            return await self._open_trade_inner(signal, signal_id)

    async def _open_trade_inner(self, signal: dict, signal_id: int = None) -> dict:
        log.info(f"open_trade: {signal.get('coin')} {signal.get('direction')} Grade:{signal.get('grade')}")

        if not state_manager.can_open_trade():
            tier = get_current_tier()
            return {"success": False, "reason": f"Max {tier['max_trades']} concurrent trades reached"}

        coin = signal.get("coin", "")
        tier = get_current_tier()

        current_price = get_current_price(coin)
        if current_price and signal.get("entry"):
            deviation = abs(current_price - signal["entry"]) / signal["entry"]
            if deviation > ENTRY_TOL:
                return {"success": False, "reason": f"Entry price moved {deviation*100:.2f}% — signal stale"}

        daily = state_manager.can_trade_today()
        if not daily["allowed"]:
            await send(f"🚫 *Daily Cap*\n{daily['reason']}")
            return {"success": False, "reason": daily["reason"]}

        check = risk_guard.pre_trade_check(signal)
        if not check["allowed"]:
            reasons = "\n".join(check["reasons"])
            await send(f"⚠️ *Trade Blocked*\n\n`{coin}`\n`{reasons}`")
            return {"success": False, "reason": reasons}

        sizing    = check["sizing"]
        direction = signal["direction"]
        leverage  = tier["leverage"]

        _ensure_isolated_margin(coin)
        set_leverage(coin, leverage)

        quantity = calculate_quantity(coin, sizing["pos_size"], signal["entry"])
        if quantity <= 0:
            await send(f"⚠️ *Trade Blocked*\n\n`{coin}`\nQuantity calculation failed")
            return {"success": False, "reason": "Quantity calculation failed"}

        cached        = None
        regime_label  = ""
        session_label = ""
        try:
            from data.cache import cache
            cached        = cache.get_raw(f"signal_{coin}")
            regime_label  = cached.get("regime", "")  if cached else ""
            session_label = cached.get("session", "") if cached else ""
        except Exception:
            pass

        import runtime_state as rs
        balance_now = rs.get_balance_cache().get("balance", cfg.CAPITAL)

        with get_session() as db:
            trade = Trade(
                signal_id        = signal_id,
                coin             = coin,
                direction        = direction,
                grade            = signal["grade"],
                state            = TradeState.ENTRY,
                is_active        = True,
                entry_price      = signal["entry"],
                sl_price         = signal["sl"],
                tp1_price        = signal["tp1"],
                tp2_price        = signal["tp2"],
                position_size    = sizing["pos_size"],
                margin_used      = sizing["margin"],
                leverage         = leverage,
                risk_amt         = sizing["risk_amt"],
                trade_date       = str(datetime.now(timezone.utc).date()),
                regime_at_entry  = regime_label,
                session_at_entry = session_label,
                score_at_entry   = signal.get("score"),
                balance_at_open  = balance_now,
                tier_at_open     = tier["tier"],
            )
            db.add(trade)
            db.flush()
            db.refresh(trade)

        state_manager.set_entry(trade)

        entry_order = place_market_order(coin=coin, direction=direction, quantity=quantity)
        if not entry_order:
            state_manager.undo_trade_open(trade.id)
            await self._abort_trade(trade, "Entry order failed")
            return {"success": False, "reason": "Entry order failed"}

        sl_order = place_sl_order(coin=coin, direction=direction,
                                  quantity=quantity, sl_price=signal["sl"])
        if not sl_order:
            close_position_market(coin, direction, quantity)
            state_manager.undo_trade_open(trade.id)
            await self._abort_trade(trade, "SL order failed — position closed")
            return {"success": False, "reason": "SL order failed"}

        tp1_qty   = round(quantity * 0.70, 3)
        tp1_order = place_tp_order(coin=coin, direction=direction,
                                   quantity=tp1_qty, tp_price=signal["tp1"], label="TP1")

        tp2_qty   = round(quantity * 0.30, 3)
        tp2_order = place_tp_order(coin=coin, direction=direction,
                                   quantity=tp2_qty, tp_price=signal["tp2"], label="TP2")

        with get_session() as db:
            t = db.query(Trade).filter(Trade.id == trade.id).first()
            t.entry_order_id = str(entry_order["id"])
            t.sl_order_id    = str(sl_order["id"])
            if tp1_order:
                t.tp1_order_id = str(tp1_order["id"])
            if tp2_order:
                t.tp2_order_id = str(tp2_order["id"])
            t.notes = f"qty_total:{quantity},qty_tp1:{tp1_qty},qty_tp2:{tp2_qty}"
            trade.entry_order_id = t.entry_order_id
            trade.sl_order_id    = t.sl_order_id
            trade.tp1_order_id   = t.tp1_order_id
            trade.tp2_order_id   = t.tp2_order_id
            trade.notes          = t.notes

        state_manager.set_in_trade(trade)
        state_manager.record_trade_open()

        from trade.price_feed import price_feed
        await price_feed.start(coin)

        await self._send_entry_alert(trade, signal, sizing)

        from events import emit
        asyncio.create_task(emit("trade_opened"))

        log.info(f"Trade opened: {coin} {direction} @ {signal['entry']} Grade:{signal['grade']}")
        return {"success": True, "trade_id": trade.id, "coin": coin, "direction": direction}

    async def reconcile_orders(self, trade: Trade):
        from trade.orders import paper_store
        missing = []

        if trade.sl_order_id:
            o = paper_store.get_order(str(trade.sl_order_id))
            if not o or o["status"] != "open":
                missing.append("SL")
        if trade.tp1_order_id and not state_manager.is_tp1_hit_for(trade.id):
            o = paper_store.get_order(str(trade.tp1_order_id))
            if not o or o["status"] != "open":
                missing.append("TP1")
        if trade.tp2_order_id:
            o = paper_store.get_order(str(trade.tp2_order_id))
            if not o or o["status"] != "open":
                missing.append("TP2")

        if not missing:
            return

        log.warning(f"Reconcile: missing {missing} for {trade.coin}")
        qty_tp1, qty_tp2 = self._parse_quantities(trade)
        total_qty = qty_tp1 + qty_tp2

        if "SL" in missing:
            sl_qty = qty_tp2 if state_manager.is_tp1_hit_for(trade.id) else total_qty
            new_sl = place_sl_order(coin=trade.coin, direction=trade.direction,
                                    quantity=sl_qty, sl_price=trade.sl_price)
            if new_sl:
                with get_session() as db:
                    t = db.query(Trade).filter(Trade.id == trade.id).first()
                    if t:
                        t.sl_order_id = str(new_sl["id"])

        if "TP1" in missing and not state_manager.is_tp1_hit_for(trade.id):
            new_tp1 = place_tp_order(coin=trade.coin, direction=trade.direction,
                                     quantity=qty_tp1, tp_price=trade.tp1_price, label="TP1")
            if new_tp1:
                with get_session() as db:
                    t = db.query(Trade).filter(Trade.id == trade.id).first()
                    if t:
                        t.tp1_order_id = str(new_tp1["id"])

        if "TP2" in missing:
            new_tp2 = place_tp_order(coin=trade.coin, direction=trade.direction,
                                     quantity=qty_tp2, tp_price=trade.tp2_price, label="TP2")
            if new_tp2:
                with get_session() as db:
                    t = db.query(Trade).filter(Trade.id == trade.id).first()
                    if t:
                        t.tp2_order_id = str(new_tp2["id"])

        await send(
            f"🔧 *Order Reconciliation*\n\n"
            f"Missing: `{', '.join(missing)}`\n"
            f"Coin: `{trade.coin}USDT {trade.direction}`\n"
            f"Orders recreated. Verify with /status"
        )

    async def _run_health_check(self, trade_obj: Trade, current_price: float):
        try:
            from data.cache import cache
            from engines.health import check_trade_health, format_health_alert

            cached = cache.get_raw(f"signal_{trade_obj.coin}")
            if not cached:
                log.warning(f"Health check: no cache for {trade_obj.coin} — using last known state")
                asyncio.create_task(self._background_analyze(trade_obj.coin))
                return

            health = check_trade_health(
                trade           = trade_obj,
                current_price   = current_price,
                d1d             = cached.get("d1d", {}),
                d4h             = cached.get("d4h", {}),
                btc_data        = cache.get_raw("btc_1d_data"),
                oi_matrix       = cached.get("oi_matrix", {}),
                retest          = cached.get("retest", {}),
                sweep           = cached.get("sweep", {}),
                original_thesis = cached.get("explanation", {}).get("thesis", ""),
                current_state   = state_manager.health_state_for(trade_obj.id)
            )

            prev_state = state_manager.health_state_for(trade_obj.id)
            state_manager.update_health(health, trade_obj.id)

            if health["state"] != prev_state:
                await send(format_health_alert(health, trade_obj.coin))
                log.info(f"Health: {prev_state} → {health['state']} for {trade_obj.coin}")

                from events import emit
                asyncio.create_task(emit("health_changed"))

        except Exception as e:
            log.debug(f"Health check error: {e}")

    async def _background_analyze(self, coin: str):
        try:
            from alerts.scanner import analyze_coin
            await analyze_coin(coin)
        except Exception as e:
            log.warning(f"Background analyze failed {coin}: {e}")

    async def _handle_tp1_hit(self, trade: Trade, current_price: float):
        qty_tp1, qty_tp2 = self._parse_quantities(trade)

        if trade.sl_order_id:
            cancel_order(trade.coin, str(trade.sl_order_id))

        new_sl = place_sl_order(coin=trade.coin, direction=trade.direction,
                                quantity=qty_tp2, sl_price=trade.entry_price)

        if trade.direction == "LONG":
            tp1_pnl = (trade.tp1_price - trade.entry_price) / trade.entry_price * (trade.position_size * 0.70)
        else:
            tp1_pnl = (trade.entry_price - trade.tp1_price) / trade.entry_price * (trade.position_size * 0.70)

        tp1_pnl = round(tp1_pnl - (trade.position_size * 0.70) * TAKER_FEE * 2, 4)

        with get_session() as db:
            t = db.query(Trade).filter(Trade.id == trade.id).first()
            t.sl_price     = trade.entry_price
            t.tp1_order_id = None
            t.tp1_hit      = True
            t.partial_pnl  = tp1_pnl
            if new_sl:
                t.sl_order_id = str(new_sl["id"])

        state_manager.record_partial_pnl(tp1_pnl)

        if not new_sl:
            await send(f"⚠️ *TP1 Hit — BE SL Failed*\n{trade.coin} — Monitor manually")
            return

        await send(
            f"⚡ *TP1 Hit — {trade.coin}*\n\n"
            f"Partial PnL: `+${tp1_pnl}`\n"
            f"SL → Breakeven: `{trade.entry_price}`\n"
            f"30% running to TP2: `{trade.tp2_price}`\n\n"
            f"Risk-free trade ✅"
        )

        from events import emit
        asyncio.create_task(emit("trade_opened"))

    async def _close_trade(self, trade: Trade, exit_price: float,
                           outcome: str, close_reason: str, phase: int = 1):
        active_size = trade.position_size if phase == 1 else trade.position_size * 0.30

        if trade.direction == "LONG":
            gross_pnl = (exit_price - trade.entry_price) / trade.entry_price * active_size
        else:
            gross_pnl = (trade.entry_price - exit_price) / trade.entry_price * active_size

        pnl             = round(gross_pnl - active_size * TAKER_FEE * 2, 4)
        health_at_close = state_manager.health_state_for(trade.id)

        with get_session() as db:
            t                 = db.query(Trade).filter(Trade.id == trade.id).first()
            t.state           = TradeState.EXIT
            t.is_active       = False
            t.outcome         = outcome
            t.exit_price      = exit_price
            t.pnl             = pnl
            t.close_reason    = close_reason
            t.closed_at       = datetime.now(timezone.utc)
            t.health_at_close = health_at_close

            if t.signal_id:
                sig = db.query(SignalModel).filter(SignalModel.id == t.signal_id).first()
                if sig:
                    sig.outcome    = outcome
                    sig.exit_price = exit_price
                    sig.pnl        = pnl

        state_manager.record_trade_close(pnl)
        state_manager.set_idle(trade.id)

        from trade.price_feed import price_feed
        if state_manager.is_idle:
            await price_feed.stop()
        else:
            await price_feed.remove_coin(trade.coin)

        await self._send_close_alert(trade, exit_price, pnl, outcome, close_reason)

        try:
            from alerts.briefing import send_post_trade_debrief
            await send_post_trade_debrief(
                trade=trade, outcome=outcome, pnl=pnl,
                close_reason=close_reason, health_at_close=health_at_close
            )
        except Exception as e:
            log.error(f"Post-trade debrief error: {e}")

        import runtime_state as rs
        rs.set_tier_config(get_current_tier())

        from events import emit
        asyncio.create_task(emit("trade_closed"))

        log.info(f"Trade closed: {trade.coin} {outcome} PnL:${pnl} Reason:{close_reason}")

    async def manual_close(self, trade_id: int = None) -> dict:
        if state_manager.is_idle:
            return {"success": False, "reason": "No active trade"}

        if trade_id:
            trade_obj = state_manager.active_trades.get(trade_id)
        else:
            trade_obj = state_manager.current_trade

        if not trade_obj:
            return {"success": False, "reason": "Trade not found"}

        with get_session() as db:
            trade = db.query(Trade).filter(Trade.id == trade_obj.id).first()

        if not trade:
            return {"success": False, "reason": "Trade not found in DB"}

        for oid in [trade.sl_order_id, trade.tp1_order_id, trade.tp2_order_id]:
            if oid:
                cancel_order(trade.coin, str(oid))

        tp1_hit    = state_manager.is_tp1_hit_for(trade.id)
        _, qty_tp2 = self._parse_quantities(trade)

        qty = calculate_quantity(
            coin     = trade.coin,
            pos_size = trade.position_size * 0.30 if tp1_hit else trade.position_size,
            price    = trade.entry_price
        )

        close_order = close_position_market(trade.coin, trade.direction, qty)
        if not close_order:
            return {"success": False, "reason": "Close order failed"}

        current_price = get_current_price(trade.coin)
        await self._close_trade(trade, current_price, "manual", "MANUAL",
                                 2 if tp1_hit else 1)

        return {"success": True, "reason": "Trade closed manually"}

    async def _abort_trade(self, trade: Trade, reason: str):
        try:
            with get_session() as db:
                t = db.query(Trade).filter(Trade.id == trade.id).first()
                if t:
                    t.is_active = False
                    t.state     = TradeState.IDLE
                    t.outcome   = "aborted"
                    t.notes     = reason
        except Exception as e:
            log.error(f"Abort trade DB error: {e}")

        state_manager.set_idle(trade.id)
        log.warning(f"Trade aborted: {reason}")
        await send(f"⚠️ *Trade Aborted*\n\nReason: {reason}\nBot is idle — scanning continues")

    def _parse_quantities(self, trade: Trade) -> tuple:
        try:
            if trade.notes:
                parts = dict(p.split(":") for p in trade.notes.split(",") if ":" in p)
                return (float(parts.get("qty_tp1", 0)), float(parts.get("qty_tp2", 0)))
        except Exception:
            log.warning(f"Quantity parse fallback: trade {trade.id}")

        total = trade.position_size or 0
        price = trade.entry_price or 1
        qty   = total / price
        return (round(qty * 0.70, 3), round(qty * 0.30, 3))

    async def _send_entry_alert(self, trade: Trade, signal: dict, sizing: dict):
        emoji     = "🏆" if trade.grade == "A+" else "✅"
        dir_emoji = "📈" if trade.direction == "LONG" else "📉"
        tier      = get_current_tier()

        tv_4h = f"https://www.tradingview.com/chart/?symbol=BINANCE:{trade.coin}USDT&interval=240"
        tv_1d = f"https://www.tradingview.com/chart/?symbol=BINANCE:{trade.coin}USDT&interval=D"

        explanation = signal.get("explanation", {})
        thesis      = explanation.get("thesis", "")
        risk_thesis = explanation.get("risk_thesis", "")
        conf_label  = explanation.get("confidence_label", "")

        active_count = len(state_manager.active_trades)
        max_trades   = tier["max_trades"]

        await send(
            f"{emoji} *Grade {trade.grade} — TRADE OPENED*\n\n"
            f"{dir_emoji} *{trade.coin}USDT {trade.direction}*\n"
            f"{'Confidence: `' + conf_label + '`' + chr(10) if conf_label else ''}"
            f"Slot: `{active_count}/{max_trades}`\n"
            f"Tier: `{tier['tier']}` · Balance: `${tier['balance']:.2f}`\n"
            f"Time: `{now_ist()}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Entry:  `{trade.entry_price}`\n"
            f"SL:     `{trade.sl_price}`\n"
            f"TP1:    `{trade.tp1_price}` (70%)\n"
            f"TP2:    `{trade.tp2_price}` (30%)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Risk:   `${sizing['risk_amt']}`\n"
            f"Size:   `${sizing['pos_size']}`\n"
            f"Lev:    `{tier['leverage']}x`\n"
            f"{chr(10) + '*Why:* ' + thesis + chr(10) if thesis else ''}"
            f"{chr(10) + '*Risk:* ' + risk_thesis + chr(10) if risk_thesis else ''}"
            f"📊 [4H]({tv_4h}) · [1D]({tv_1d})\n\n"
            f"Type /status to monitor"
        )

    async def _send_close_alert(self, trade: Trade, exit_price: float,
                                pnl: float, outcome: str, close_reason: str):
        emoji     = "✅" if outcome == "win" else "❌" if outcome == "loss" else "⏹"
        pnl_emoji = "📈" if pnl >= 0 else "📉"
        tv_4h     = f"https://www.tradingview.com/chart/?symbol=BINANCE:{trade.coin}USDT&interval=240"

        remaining = len(state_manager.active_trades)

        await send(
            f"{emoji} *Trade Closed — {close_reason}*\n\n"
            f"*{trade.coin}USDT {trade.direction}*\n"
            f"Time: `{now_ist()}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Entry:   `{trade.entry_price}`\n"
            f"Exit:    `{exit_price}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{pnl_emoji} PnL:    `${pnl}`\n"
            f"Outcome: `{outcome.upper()}`\n"
            f"Health:  `{state_manager.health_state_for(trade.id)}`\n\n"
            f"Active trades remaining: `{remaining}`\n"
            f"📊 [4H]({tv_4h})\n\n"
            f"Type /pnl for stats"
        )


trade_manager = TradeManager()