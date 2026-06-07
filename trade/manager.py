import asyncio
import logging
from datetime import datetime, timezone
from database import (
    SessionLocal, Trade,
    Signal as SignalModel
)
from trade.state import state_manager, TradeState
from trade.risk import risk_guard
from trade.orders import (
    set_leverage, place_market_order,
    place_sl_order, place_tp_order,
    cancel_order, get_order_status,
    get_current_price, close_position_market,
    calculate_quantity
)
from alerts.telegram import send, now_ist
from config import cfg

log = logging.getLogger(__name__)

TAKER_FEE = 0.0006


class TradeManager:

    def __init__(self):
        self._last_db_update = 0

    async def on_price_update(self, coin: str, price: float):
        if state_manager.is_idle:
            return

        trade = state_manager.current_trade
        if not trade or trade.coin != coin:
            return

        now = asyncio.get_event_loop().time()
        if now - self._last_db_update > 10:
            db = SessionLocal()
            try:
                t = db.query(Trade).filter(Trade.id == trade.id).first()
                if t:
                    t.current_price = price
                    db.commit()
            finally:
                db.close()
            self._last_db_update = now

        await self._check_sl_tp(trade, price)

    async def _check_sl_tp(self, trade, current_price: float):
        tp1_already_hit = (
            abs(trade.sl_price - trade.entry_price) /
            trade.entry_price < 0.001
            if trade.sl_price and trade.entry_price
            else False
        )

        def get_trade_from_db():
            db = SessionLocal()
            try:
                return db.query(Trade).filter(
                    Trade.id == trade.id
                ).first()
            finally:
                db.close()

        if not tp1_already_hit:
            if trade.sl_order_id:
                sl_status = get_order_status(
                    trade.coin, str(trade.sl_order_id)
                )
                if sl_status and sl_status["status"] == "closed":
                    log.info(f"SL hit: {trade.coin} @ {current_price}")
                    await self._close_trade(
                        trade        = get_trade_from_db(),
                        exit_price   = current_price,
                        outcome      = "loss",
                        close_reason = "SL",
                        phase        = 1
                    )
                    return

            if trade.tp1_order_id:
                tp1_status = get_order_status(
                    trade.coin, str(trade.tp1_order_id)
                )
                if tp1_status and tp1_status["status"] == "closed":
                    log.info(f"TP1 hit: {trade.coin} @ {current_price}")
                    await self._handle_tp1_hit(
                        get_trade_from_db(), current_price
                    )
                    return
        else:
            if trade.sl_order_id:
                sl_status = get_order_status(
                    trade.coin, str(trade.sl_order_id)
                )
                if sl_status and sl_status["status"] == "closed":
                    log.info(f"BE SL hit: {trade.coin}")
                    await self._close_trade(
                        trade        = get_trade_from_db(),
                        exit_price   = trade.entry_price,
                        outcome      = "win",
                        close_reason = "TP1 + BE",
                        phase        = 2
                    )
                    return

            if trade.tp2_order_id:
                tp2_status = get_order_status(
                    trade.coin, str(trade.tp2_order_id)
                )
                if tp2_status and tp2_status["status"] == "closed":
                    log.info(f"TP2 hit: {trade.coin} @ {current_price}")
                    await self._close_trade(
                        trade        = get_trade_from_db(),
                        exit_price   = current_price,
                        outcome      = "win",
                        close_reason = "TP2",
                        phase        = 2
                    )
                    return

    async def run_health_check_only(self):
        if state_manager.is_idle:
            return

        trade = state_manager.current_trade
        if not trade:
            return

        from trade.price_feed import price_feed
        current = price_feed.get_price(trade.coin)
        if not current:
            current = get_current_price(trade.coin)

        db = SessionLocal()
        try:
            t = db.query(Trade).filter(Trade.id == trade.id).first()
        finally:
            db.close()

        await self._run_health_check(
            trade_obj     = t,
            current_price = current
        )

    async def open_trade(
        self,
        signal:    dict,
        signal_id: int = None
    ) -> dict:

        log.info(
            f"open_trade: {signal.get('coin')} "
            f"{signal.get('direction')} "
            f"Grade:{signal.get('grade')} "
            f"Score:{signal.get('score')}"
        )

        if not state_manager.is_idle:
            trade = state_manager.current_trade
            log.info(
                f"Already in trade: "
                f"{trade.coin if trade else 'unknown'}"
            )
            return {"success": False, "reason": "Already in trade"}

        daily = state_manager.can_trade_today()
        if not daily["allowed"]:
            log.warning(f"Daily cap blocked: {daily['reason']}")
            await send(f"🚫 *Daily Cap*\n{daily['reason']}")
            return {"success": False, "reason": daily["reason"]}

        check = risk_guard.pre_trade_check(signal)
        if not check["allowed"]:
            reasons = "\n".join(check["reasons"])
            log.warning(f"Pre trade check FAILED:\n{reasons}")
            await send(
                f"⚠️ *Trade Blocked*\n\n"
                f"Coin: `{signal.get('coin')}`\n"
                f"Grade: `{signal.get('grade')}`\n\n"
                f"Reason:\n`{reasons}`"
            )
            return {"success": False, "reason": reasons}

        sizing    = check["sizing"]
        coin      = signal["coin"]
        direction = signal["direction"]

        set_leverage(coin, cfg.LEVERAGE)

        quantity = calculate_quantity(
            coin     = coin,
            pos_size = sizing["pos_size"],
            price    = signal["entry"]
        )

        if quantity <= 0:
            await send(
                f"⚠️ *Trade Blocked*\n\n"
                f"Coin: `{coin}`\n"
                f"Reason: `Quantity calculation failed`"
            )
            return {"success": False, "reason": "Quantity calculation failed"}

        db = SessionLocal()
        try:
            trade = Trade(
                signal_id     = signal_id,
                coin          = coin,
                direction     = direction,
                grade         = signal["grade"],
                state         = TradeState.ENTRY,
                is_active     = True,
                entry_price   = signal["entry"],
                sl_price      = signal["sl"],
                tp1_price     = signal["tp1"],
                tp2_price     = signal["tp2"],
                position_size = sizing["pos_size"],
                margin_used   = sizing["margin"],
                leverage      = cfg.LEVERAGE,
                risk_amt      = sizing["risk_amt"],
                trade_date    = str(datetime.now(timezone.utc).date())
            )
            db.add(trade)
            db.commit()
            db.refresh(trade)
        finally:
            db.close()

        state_manager.set_entry(trade)

        entry_order = place_market_order(
            coin      = coin,
            direction = direction,
            quantity  = quantity
        )

        if not entry_order:
            await self._abort_trade(trade, "Entry order failed")
            return {"success": False, "reason": "Entry order failed"}

        sl_order = place_sl_order(
            coin      = coin,
            direction = direction,
            quantity  = quantity,
            sl_price  = signal["sl"]
        )

        if not sl_order:
            close_position_market(coin, direction, quantity)
            await self._abort_trade(
                trade, "SL order failed — position closed"
            )
            return {"success": False, "reason": "SL order failed"}

        tp1_qty   = round(quantity * 0.70, 3)
        tp1_order = place_tp_order(
            coin      = coin,
            direction = direction,
            quantity  = tp1_qty,
            tp_price  = signal["tp1"],
            label     = "TP1"
        )

        tp2_qty   = round(quantity * 0.30, 3)
        tp2_order = place_tp_order(
            coin      = coin,
            direction = direction,
            quantity  = tp2_qty,
            tp_price  = signal["tp2"],
            label     = "TP2"
        )

        db = SessionLocal()
        try:
            t = db.query(Trade).filter(Trade.id == trade.id).first()
            t.entry_order_id = str(entry_order["id"])
            t.sl_order_id    = str(sl_order["id"])
            if tp1_order:
                t.tp1_order_id = str(tp1_order["id"])
            if tp2_order:
                t.tp2_order_id = str(tp2_order["id"])
            t.notes = (
                f"qty_total:{quantity},"
                f"qty_tp1:{tp1_qty},"
                f"qty_tp2:{tp2_qty}"
            )
            db.commit()
            trade.entry_order_id = t.entry_order_id
            trade.sl_order_id    = t.sl_order_id
            trade.tp1_order_id   = t.tp1_order_id
            trade.tp2_order_id   = t.tp2_order_id
            trade.notes          = t.notes
        finally:
            db.close()

        state_manager.set_in_trade(trade)
        state_manager.record_trade_open()

        from trade.price_feed import price_feed
        await price_feed.start(coin)

        await self._send_entry_alert(trade, signal, sizing)

        log.info(
            f"Trade opened: {coin} {direction} "
            f"@ {signal['entry']} "
            f"Grade:{signal['grade']} "
            f"SL:{signal['sl']} "
            f"TP1:{signal['tp1']} "
            f"TP2:{signal['tp2']}"
        )

        return {
            "success":   True,
            "trade_id":  trade.id,
            "coin":      coin,
            "direction": direction
        }

    async def _run_health_check(
        self,
        trade_obj:     Trade,
        current_price: float
    ):
        try:
            from data.cache import cache
            from engines.health import check_trade_health, format_health_alert

            coin   = trade_obj.coin
            cached = cache.get(f"signal_{coin}")
            if not cached:
                return

            health = check_trade_health(
                trade           = trade_obj,
                current_price   = current_price,
                d1d             = cached.get("d1d", {}),
                d4h             = cached.get("d4h", {}),
                btc_data        = cache.get("btc_1d_data"),
                oi_matrix       = cached.get("wconf", {}),
                retest          = cached.get("retest", {}),
                sweep           = cached.get("sweep", {}),
                original_thesis = cached.get(
                    "explanation", {}
                ).get("thesis", "")
            )

            prev_state = state_manager.health_state
            state_manager.update_health(health)

            if health["state"] != prev_state:
                await send(format_health_alert(health, coin))
                log.info(
                    f"Health: {prev_state} → "
                    f"{health['state']} for {coin}"
                )

        except Exception as e:
            log.debug(f"Health check error: {e}")

    def _is_tp1_already_hit(self, trade: Trade) -> bool:
        if not trade.sl_price or not trade.entry_price:
            return False
        return (
            abs(trade.sl_price - trade.entry_price) /
            trade.entry_price < 0.001
        )

    async def _handle_tp1_hit(
        self,
        trade:         Trade,
        current_price: float
    ):
        qty_tp1, qty_tp2 = self._parse_quantities(trade)

        if trade.sl_order_id:
            cancel_order(trade.coin, str(trade.sl_order_id))

        new_sl = place_sl_order(
            coin      = trade.coin,
            direction = trade.direction,
            quantity  = qty_tp2,
            sl_price  = trade.entry_price
        )

        db = SessionLocal()
        try:
            t = db.query(Trade).filter(Trade.id == trade.id).first()
            t.sl_price     = trade.entry_price
            t.tp1_order_id = None
            if new_sl:
                t.sl_order_id = str(new_sl["id"])
            db.commit()
        finally:
            db.close()

        if trade.direction == "LONG":
            tp1_pnl = (
                (trade.tp1_price - trade.entry_price) /
                trade.entry_price *
                (trade.position_size * 0.70)
            )
        else:
            tp1_pnl = (
                (trade.entry_price - trade.tp1_price) /
                trade.entry_price *
                (trade.position_size * 0.70)
            )

        tp1_pnl = round(
            tp1_pnl -
            (trade.position_size * 0.70) * TAKER_FEE * 2,
            4
        )
        state_manager.record_partial_pnl(tp1_pnl)

        log.info(
            f"TP1 hit: {trade.coin} "
            f"partial_pnl:${tp1_pnl} "
            f"BE SL @ {trade.entry_price}"
        )

        if not new_sl:
            await send(
                f"⚠️ *TP1 Hit — BE SL Failed*\n"
                f"{trade.coin} — Monitor manually\n"
                f"Use /close if needed"
            )
            return

        await send(
            f"⚡ *TP1 Hit — {trade.coin}*\n\n"
            f"Partial PnL: `+${tp1_pnl}`\n"
            f"SL → Breakeven: `{trade.entry_price}`\n"
            f"30% running to TP2: `{trade.tp2_price}`\n\n"
            f"Risk-free trade ✅"
        )

    async def _close_trade(
        self,
        trade:        Trade,
        exit_price:   float,
        outcome:      str,
        close_reason: str,
        phase:        int = 1
    ):
        active_size = (
            trade.position_size
            if phase == 1
            else trade.position_size * 0.30
        )

        if trade.direction == "LONG":
            gross_pnl = (
                (exit_price - trade.entry_price) /
                trade.entry_price * active_size
            )
        else:
            gross_pnl = (
                (trade.entry_price - exit_price) /
                trade.entry_price * active_size
            )

        pnl             = round(
            gross_pnl - active_size * TAKER_FEE * 2, 4
        )
        health_at_close = state_manager.health_state

        db = SessionLocal()
        try:
            t                 = db.query(Trade).filter(
                Trade.id == trade.id
            ).first()
            t.state           = TradeState.EXIT
            t.is_active       = False
            t.outcome         = outcome
            t.exit_price      = exit_price
            t.pnl             = pnl
            t.close_reason    = close_reason
            t.closed_at       = datetime.now(timezone.utc)
            t.health_at_close = health_at_close
            db.commit()

            if t.signal_id:
                sig = db.query(SignalModel).filter(
                    SignalModel.id == t.signal_id
                ).first()
                if sig:
                    sig.outcome    = outcome
                    sig.exit_price = exit_price
                    sig.pnl        = pnl
                    db.commit()
        finally:
            db.close()

        state_manager.record_trade_close(pnl)
        state_manager.set_idle()

        from trade.price_feed import price_feed
        await price_feed.stop()

        await self._send_close_alert(
            trade, exit_price, pnl, outcome, close_reason
        )

        # Post-trade debrief
        try:
            from alerts.briefing import send_post_trade_debrief
            await send_post_trade_debrief(
                trade            = trade,
                outcome          = outcome,
                pnl              = pnl,
                close_reason     = close_reason,
                health_at_close  = health_at_close
            )
        except Exception as e:
            log.error(f"Post-trade debrief error: {e}")

        log.info(
            f"Trade closed: {trade.coin} "
            f"{outcome} phase:{phase} "
            f"PnL:${pnl} "
            f"Reason:{close_reason} "
            f"Health:{health_at_close}"
        )

    async def manual_close(self) -> dict:
        if state_manager.is_idle:
            return {"success": False, "reason": "No active trade"}

        trade_id = state_manager.current_trade.id
        db       = SessionLocal()
        try:
            trade = db.query(Trade).filter(
                Trade.id == trade_id
            ).first()
        finally:
            db.close()

        if not trade:
            return {"success": False, "reason": "Trade not found"}

        for oid in [
            trade.sl_order_id,
            trade.tp1_order_id,
            trade.tp2_order_id
        ]:
            if oid:
                cancel_order(trade.coin, str(oid))

        tp1_hit    = self._is_tp1_already_hit(trade)
        _, qty_tp2 = self._parse_quantities(trade)

        qty = calculate_quantity(
            coin     = trade.coin,
            pos_size = (
                trade.position_size * 0.30
                if tp1_hit
                else trade.position_size
            ),
            price    = trade.entry_price
        )

        close_order = close_position_market(
            coin      = trade.coin,
            direction = trade.direction,
            quantity  = qty
        )

        if not close_order:
            return {"success": False, "reason": "Close order failed"}

        current_price = get_current_price(trade.coin)

        await self._close_trade(
            trade        = trade,
            exit_price   = current_price,
            outcome      = "manual",
            close_reason = "MANUAL",
            phase        = 2 if tp1_hit else 1
        )

        return {"success": True, "reason": "Trade closed manually"}

    async def _abort_trade(self, trade: Trade, reason: str):
        db = SessionLocal()
        try:
            t = db.query(Trade).filter(Trade.id == trade.id).first()
            if t:
                t.is_active = False
                t.state     = TradeState.IDLE
                t.outcome   = "aborted"
                t.notes     = reason
                db.commit()
        finally:
            db.close()

        state_manager.set_idle()
        log.warning(f"Trade aborted: {reason}")
        await send(
            f"⚠️ *Trade Aborted*\n\n"
            f"Reason: {reason}\n"
            f"Bot is idle — scanning continues"
        )

    def _parse_quantities(self, trade: Trade) -> tuple:
        try:
            if trade.notes:
                parts = dict(
                    p.split(":")
                    for p in trade.notes.split(",")
                    if ":" in p
                )
                return (
                    float(parts.get("qty_tp1", 0)),
                    float(parts.get("qty_tp2", 0))
                )
        except Exception:
            log.warning(
                f"Quantity parse fallback: "
                f"trade {trade.id} notes: {trade.notes}"
            )

        total = trade.position_size or 0
        price = trade.entry_price or 1
        qty   = total / price
        return (round(qty * 0.70, 3), round(qty * 0.30, 3))

    async def _send_entry_alert(self, trade, signal, sizing):
        emoji     = "🏆" if trade.grade == "A+" else "✅"
        dir_emoji = "📈" if trade.direction == "LONG" else "📉"

        tv_4h = (
            f"https://www.tradingview.com/chart/"
            f"?symbol=BINANCE:{trade.coin}USDT&interval=240"
        )
        tv_1d = (
            f"https://www.tradingview.com/chart/"
            f"?symbol=BINANCE:{trade.coin}USDT&interval=D"
        )

        explanation = signal.get("explanation", {})
        thesis      = explanation.get("thesis", "")
        risk_thesis = explanation.get("risk_thesis", "")
        conf_label  = explanation.get("confidence_label", "")

        thesis_block = f"\n*Why This Trade?*\n{thesis}\n" if thesis else ""
        risk_block   = f"\n*Risk Factors*\n{risk_thesis}\n" if risk_thesis else ""
        conf_block   = f"Confidence: `{conf_label}`\n" if conf_label else ""

        await send(
            f"{emoji} *Grade {trade.grade} — TRADE OPENED*\n\n"
            f"{dir_emoji} *{trade.coin}USDT {trade.direction}*\n"
            f"{conf_block}"
            f"Time: `{now_ist()}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Entry:  `{trade.entry_price}`\n"
            f"SL:     `{trade.sl_price}`\n"
            f"TP1:    `{trade.tp1_price}` (70%)\n"
            f"TP2:    `{trade.tp2_price}` (30%)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Risk:   `${sizing['risk_amt']}`\n"
            f"Size:   `${sizing['pos_size']}`\n"
            f"Lev:    `{cfg.LEVERAGE}x`\n"
            f"{thesis_block}"
            f"{risk_block}"
            f"📊 [4H Chart]({tv_4h})\n"
            f"📅 [Daily Chart]({tv_1d})\n\n"
            f"Type /status to monitor"
        )

    async def _send_close_alert(
        self, trade, exit_price, pnl, outcome, close_reason
    ):
        emoji     = (
            "✅" if outcome == "win"  else
            "❌" if outcome == "loss" else
            "⏹"
        )
        pnl_emoji = "📈" if pnl >= 0 else "📉"

        tv_4h = (
            f"https://www.tradingview.com/chart/"
            f"?symbol=BINANCE:{trade.coin}USDT&interval=240"
        )

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
            f"Health:  `{state_manager.health_state}`\n\n"
            f"📊 [4H Chart]({tv_4h})\n\n"
            f"Bot idle — scanning for next signal\n"
            f"Type /pnl for full stats"
        )


trade_manager = TradeManager()