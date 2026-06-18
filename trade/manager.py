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
        self._closing:        dict[int, bool]  = {}

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

        if self._closing.get(trade_id):
            return

        lock = state_manager.get_trade_lock(trade_id)
        if lock.locked():
            return

        async with lock:
            if self._closing.get(trade_id):
                return

            def fresh():
                with get_session() as db:
                    return db.query(Trade).filter(Trade.id == trade_id).first()

            t = fresh()
            if not t or not t.is_active:
                state_manager.set_idle(trade_id)
                return

            is_long  = t.direction == "LONG"
            sl_price = t.sl_price
            tp_price = t.tp1_price

            if sl_price and tp_price:
                sl_hit = (is_long and current_price <= sl_price) or \
                         (not is_long and current_price >= sl_price)
                tp_hit = (is_long and current_price >= tp_price) or \
                         (not is_long and current_price <= tp_price)

                if sl_hit:
                    self._closing[trade_id] = True
                    log.info(f"SL hit by price: {trade.coin} @ {current_price} SL:{sl_price}")
                    await self._close_trade(t, current_price, "loss", "SL")
                    return

                if tp_hit:
                    self._closing[trade_id] = True
                    log.info(f"TP hit by price: {trade.coin} @ {current_price} TP:{tp_price}")
                    await self._close_trade(t, current_price, "win", "TP")
                    return

            if t.sl_order_id:
                sl_status = get_order_status(t.coin, str(t.sl_order_id))
                if sl_status and sl_status["status"] == "closed":
                    self._closing[trade_id] = True
                    await self._close_trade(fresh(), current_price, "loss", "SL")
                    return

            if t.tp1_order_id:
                tp_status = get_order_status(t.coin, str(t.tp1_order_id))
                if tp_status and tp_status["status"] == "closed":
                    self._closing[trade_id] = True
                    await self._close_trade(fresh(), current_price, "win", "TP")
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

                log.info(f"[SYNC] Detected untracked Binance position: {coin} {direction} @ {entry}")

                import runtime_state as rs
                balance_now = rs.get_balance_cache().get("balance", cfg.CAPITAL)

                with get_session() as db:
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
                    f"`/setlevels {coin} <sl> <tp1>`\n\n"
                    f"Example:\n"
                    f"`/setlevels {coin} 0.0950 0.1100`"
                )

        except Exception as e:
            log.error(f"Binance position sync error: {e}")

    async def set_trade_levels(self, coin: str, sl: float, tp1: float, tp2: float = None) -> dict:
        trade = next(
            (t for t in state_manager.active_trades.values() if t.coin == coin),
            None
        )
        if not trade:
            return {"success": False, "reason": f"No active trade for {coin}"}

        lock = state_manager.get_trade_lock(trade.id)
        async with lock:
            with get_session() as db:
                t = db.query(Trade).filter(Trade.id == trade.id).first()
                if not t:
                    return {"success": False, "reason": "Trade not found in DB"}

                t.sl_price  = sl
                t.tp1_price = tp1
                trade.sl_price  = sl
                trade.tp1_price = tp1

                if not cfg.PAPER_TRADING:
                    qty = calculate_quantity(coin, t.position_size, t.entry_price)

                    if t.sl_order_id:
                        cancel_order(coin, str(t.sl_order_id))
                    if t.tp1_order_id:
                        cancel_order(coin, str(t.tp1_order_id))

                    new_sl = place_sl_order(coin=coin, direction=t.direction,
                                            quantity=qty, sl_price=sl)
                    new_tp = place_tp_order(coin=coin, direction=t.direction,
                                            quantity=qty, tp_price=tp1, label="TP")

                    if new_sl:
                        t.sl_order_id  = str(new_sl["id"])
                        trade.sl_order_id = str(new_sl["id"])
                    if new_tp:
                        t.tp1_order_id = str(new_tp["id"])
                        trade.tp1_order_id = str(new_tp["id"])

        log.info(f"Levels set for {coin}: SL:{sl} TP:{tp1}")
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

        already_active = any(
            t.coin == coin
            for t in state_manager.active_trades.values()
        )
        if already_active:
            log.warning(f"Trade already active for {coin} — skipping open")
            return {"success": False, "reason": f"{coin} already has active trade"}

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
                tp2_price        = None,
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

        tp_order = place_tp_order(coin=coin, direction=direction,
                                  quantity=quantity, tp_price=signal["tp1"], label="TP")

        with get_session() as db:
            t = db.query(Trade).filter(Trade.id == trade.id).first()
            t.entry_order_id = str(entry_order["id"])
            t.sl_order_id    = str(sl_order["id"])
            if tp_order:
                t.tp1_order_id = str(tp_order["id"])
            t.notes = f"qty_total:{quantity}"
            trade.entry_order_id = t.entry_order_id
            trade.sl_order_id    = t.sl_order_id
            trade.tp1_order_id   = t.tp1_order_id
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
        if trade.tp1_order_id:
            o = paper_store.get_order(str(trade.tp1_order_id))
            if not o or o["status"] != "open":
                missing.append("TP")

        if not missing:
            return

        log.warning(f"Reconcile: missing {missing} for {trade.coin}")
        qty = self._parse_quantity(trade)

        if "SL" in missing:
            new_sl = place_sl_order(coin=trade.coin, direction=trade.direction,
                                    quantity=qty, sl_price=trade.sl_price)
            if new_sl:
                with get_session() as db:
                    t = db.query(Trade).filter(Trade.id == trade.id).first()
                    if t:
                        t.sl_order_id = str(new_sl["id"])

        if "TP" in missing:
            new_tp = place_tp_order(coin=trade.coin, direction=trade.direction,
                                    quantity=qty, tp_price=trade.tp1_price, label="TP")
            if new_tp:
                with get_session() as db:
                    t = db.query(Trade).filter(Trade.id == trade.id).first()
                    if t:
                        t.tp1_order_id = str(new_tp["id"])

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

    async def _close_trade(self, trade: Trade, exit_price: float,
                           outcome: str, close_reason: str):
        if not trade or not trade.is_active:
            return

        pnl = 0.0
        if trade.direction == "LONG":
            gross_pnl = (exit_price - trade.entry_price) / trade.entry_price * trade.position_size
        else:
            gross_pnl = (trade.entry_price - exit_price) / trade.entry_price * trade.position_size

        pnl             = round(gross_pnl - trade.position_size * TAKER_FEE * 2, 4)
        health_at_close = state_manager.health_state_for(trade.id)

        with get_session() as db:
            t = db.query(Trade).filter(Trade.id == trade.id).first()
            if not t or not t.is_active:
                return
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

        self._closing.pop(trade.id, None)
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

        lock = state_manager.get_trade_lock(trade_obj.id)
        async with lock:
            with get_session() as db:
                trade = db.query(Trade).filter(Trade.id == trade_obj.id).first()

            if not trade:
                return {"success": False, "reason": "Trade not found in DB"}

            for oid in [trade.sl_order_id, trade.tp1_order_id, trade.tp2_order_id]:
                if oid:
                    cancel_order(trade.coin, str(oid))

            qty = self._parse_quantity(trade)

            close_order = close_position_market(trade.coin, trade.direction, qty)
            if not close_order:
                return {"success": False, "reason": "Close order failed"}

            current_price = get_current_price(trade.coin)
            self._closing[trade.id] = True
            await self._close_trade(trade, current_price, "manual", "MANUAL")

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

    def _parse_quantity(self, trade: Trade) -> float:
        try:
            if trade.notes:
                parts = dict(p.split(":") for p in trade.notes.split(",") if ":" in p)
                qty = float(parts.get("qty_total", 0))
                if qty > 0:
                    return qty
        except Exception:
            log.warning(f"Quantity parse fallback: trade {trade.id}")

        total = trade.position_size or 0
        price = trade.entry_price or 1
        return round(total / price, 3)

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
            f"TP:     `{trade.tp1_price}`\n"
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