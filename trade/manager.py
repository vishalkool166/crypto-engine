import logging
from datetime import datetime
from database import SessionLocal, Trade, Signal as SignalModel
from trade.state import state_manager, TradeState
from trade.risk import risk_guard
from trade.orders import (
    set_leverage, place_market_order,
    place_sl_order, place_tp_order,
    cancel_order, get_order_status,
    get_current_price, close_position_market,
    calculate_quantity
)
from alerts.telegram import send
from config import cfg

log = logging.getLogger(__name__)

# Taker fee both sides
TAKER_FEE = 0.0006


class TradeManager:

    # ═══════════════════════════════════════════════════
    # OPEN TRADE
    # ═══════════════════════════════════════════════════
    async def open_trade(
        self,
        signal:    dict,
        signal_id: int = None
    ) -> dict:

        if not state_manager.is_idle:
            log.info(
                f"Signal ignored — already in trade: "
                f"{state_manager.current_trade.coin}"
            )
            return {"success": False, "reason": "Already in trade"}

        daily = state_manager.can_trade_today()
        if not daily["allowed"]:
            log.warning(f"Daily cap: {daily['reason']}")
            await send(f"🚫 *Daily Cap*\n{daily['reason']}")
            return {"success": False, "reason": daily["reason"]}

        check = risk_guard.pre_trade_check(signal)
        if not check["allowed"]:
            reasons = "\n".join(check["reasons"])
            log.warning(f"Pre trade check failed:\n{reasons}")
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
            return {"success": False, "reason": "Quantity calculation failed"}

        # Create DB record
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
                trade_date    = str(datetime.utcnow().date())
            )
            db.add(trade)
            db.commit()
            db.refresh(trade)
        finally:
            db.close()

        state_manager.set_entry(trade)

        # Entry order
        entry_order = place_market_order(
            coin      = coin,
            direction = direction,
            quantity  = quantity
        )

        if not entry_order:
            await self._abort_trade(trade, "Entry order failed")
            return {"success": False, "reason": "Entry order failed"}

        # SL — critical
        sl_order = place_sl_order(
            coin      = coin,
            direction = direction,
            quantity  = quantity,
            sl_price  = signal["sl"]
        )

        if not sl_order:
            close_position_market(coin, direction, quantity)
            await self._abort_trade(trade, "SL order failed — position closed")
            return {"success": False, "reason": "SL order failed"}

        # TP1 — 70%
        tp1_qty   = round(quantity * 0.70, 3)
        tp1_order = place_tp_order(
            coin      = coin,
            direction = direction,
            quantity  = tp1_qty,
            tp_price  = signal["tp1"],
            label     = "TP1"
        )

        # TP2 — 30%
        tp2_qty   = round(quantity * 0.30, 3)
        tp2_order = place_tp_order(
            coin      = coin,
            direction = direction,
            quantity  = tp2_qty,
            tp_price  = signal["tp2"],
            label     = "TP2"
        )

        # Save order IDs + quantities to DB
        db = SessionLocal()
        try:
            t = db.query(Trade).filter(Trade.id == trade.id).first()
            t.entry_order_id = str(entry_order["id"])
            t.sl_order_id    = str(sl_order["id"])
            if tp1_order:
                t.tp1_order_id = str(tp1_order["id"])
            if tp2_order:
                t.tp2_order_id = str(tp2_order["id"])
            # Store quantities for accurate PnL
            t.notes = (
                f"qty_total:{quantity},"
                f"qty_tp1:{tp1_qty},"
                f"qty_tp2:{tp2_qty}"
            )
            db.commit()
            # Sync local object
            trade.entry_order_id = t.entry_order_id
            trade.sl_order_id    = t.sl_order_id
            trade.tp1_order_id   = t.tp1_order_id
            trade.tp2_order_id   = t.tp2_order_id
            trade.notes          = t.notes
        finally:
            db.close()

        state_manager.set_in_trade(trade)
        state_manager.record_trade_open()

        await self._send_entry_alert(trade, signal, sizing)

        log.info(
            f"Trade opened: {coin} {direction} "
            f"@ {signal['entry']} Grade:{signal['grade']}"
        )

        return {
            "success":   True,
            "trade_id":  trade.id,
            "coin":      coin,
            "direction": direction
        }


    # ═══════════════════════════════════════════════════
    # MONITOR TRADE
    # ═══════════════════════════════════════════════════
    async def monitor_trade(self):

        if state_manager.is_idle:
            return

        # Always refresh from DB — never trust stale object
        trade_id = state_manager.current_trade.id
        db       = SessionLocal()
        try:
            trade = db.query(Trade).filter(
                Trade.id == trade_id
            ).first()
        finally:
            db.close()

        if not trade or not trade.is_active:
            state_manager.set_idle()
            return

        current_price = get_current_price(trade.coin)
        if not current_price:
            log.warning(f"Could not get price: {trade.coin}")
            return

        # Update current price
        db = SessionLocal()
        try:
            t = db.query(Trade).filter(Trade.id == trade.id).first()
            if t:
                t.current_price = current_price
                db.commit()
        finally:
            db.close()

        # ── DETERMINE PHASE ──
        # Phase 1: tp1_order exists and not yet filled
        # Phase 2: tp1_order filled (tp1_order_id cleared),
        #          watching tp2 and BE SL
        tp1_already_hit = self._is_tp1_already_hit(trade)

        if not tp1_already_hit:
            # ── PHASE 1 — watching TP1 and SL ──

            # Check SL first
            if trade.sl_order_id:
                sl_status = get_order_status(
                    trade.coin, trade.sl_order_id
                )
                if sl_status and sl_status["status"] == "closed":
                    log.info(f"SL hit: {trade.coin}")
                    await self._close_trade(
                        trade        = trade,
                        exit_price   = current_price,
                        outcome      = "loss",
                        close_reason = "SL",
                        phase        = 1
                    )
                    return

            # Check TP1
            if trade.tp1_order_id:
                tp1_status = get_order_status(
                    trade.coin, trade.tp1_order_id
                )
                if tp1_status and tp1_status["status"] == "closed":
                    log.info(f"TP1 hit: {trade.coin}")
                    await self._handle_tp1_hit(
                        trade, current_price
                    )
                    return

        else:
            # ── PHASE 2 — TP1 done, watching TP2 and BE SL ──

            # Check BE SL first
            if trade.sl_order_id:
                sl_status = get_order_status(
                    trade.coin, trade.sl_order_id
                )
                if sl_status and sl_status["status"] == "closed":
                    log.info(
                        f"BE SL hit after TP1: {trade.coin}"
                    )
                    await self._close_trade(
                        trade        = trade,
                        exit_price   = trade.entry_price,
                        outcome      = "win",
                        close_reason = "TP1 + BE",
                        phase        = 2
                    )
                    return

            # Check TP2
            if trade.tp2_order_id:
                tp2_status = get_order_status(
                    trade.coin, trade.tp2_order_id
                )
                if tp2_status and tp2_status["status"] == "closed":
                    log.info(f"TP2 hit: {trade.coin}")
                    await self._close_trade(
                        trade        = trade,
                        exit_price   = current_price,
                        outcome      = "win",
                        close_reason = "TP2",
                        phase        = 2
                    )
                    return

        # Log uPnL
        upnl = risk_guard.calculate_unrealized_pnl(
            direction     = trade.direction,
            entry_price   = trade.entry_price,
            current_price = current_price,
            pos_size      = trade.position_size
        )
        log.info(
            f"Monitor [{trade.coin}] "
            f"{'Phase2-RF' if tp1_already_hit else 'Phase1'} "
            f"Entry:{trade.entry_price} "
            f"Now:{current_price} "
            f"uPnL:${upnl}"
        )


    # ═══════════════════════════════════════════════════
    # IS TP1 ALREADY HIT
    # Checks DB flag — not order status
    # Prevents re-triggering on same closed order
    # ═══════════════════════════════════════════════════
    def _is_tp1_already_hit(self, trade: Trade) -> bool:
        """
        TP1 is considered hit when:
        - sl_price has been moved to entry_price (breakeven)
        We store this in DB so it survives restarts.
        """
        if not trade.sl_price or not trade.entry_price:
            return False
        # SL within 0.1% of entry = breakeven = TP1 was hit
        return abs(trade.sl_price - trade.entry_price) \
               / trade.entry_price < 0.001


    # ═══════════════════════════════════════════════════
    # HANDLE TP1 HIT
    # ═══════════════════════════════════════════════════
    async def _handle_tp1_hit(
        self,
        trade:         Trade,
        current_price: float
    ):
        # Parse quantities from notes
        qty_tp1, qty_tp2 = self._parse_quantities(trade)

        # Cancel old full SL
        if trade.sl_order_id:
            cancel_order(trade.coin, trade.sl_order_id)

        # Place BE SL for remaining 30%
        new_sl = place_sl_order(
            coin      = trade.coin,
            direction = trade.direction,
            quantity  = qty_tp2,
            sl_price  = trade.entry_price
        )

        # ── CRITICAL: update DB immediately ──
        # Set sl_price = entry_price
        # This is the flag _is_tp1_already_hit() reads
        # Also clear tp1_order_id so we never check it again
        db = SessionLocal()
        try:
            t = db.query(Trade).filter(
                Trade.id == trade.id
            ).first()
            t.sl_price      = trade.entry_price  # ← BE flag
            t.tp1_order_id  = None               # ← clear so never re-checked
            if new_sl:
                t.sl_order_id = str(new_sl["id"])
            db.commit()
        finally:
            db.close()

        # Calculate TP1 PnL (70% of position)
        if trade.direction == "LONG":
            tp1_pnl = (
                (trade.tp1_price - trade.entry_price) /
                trade.entry_price * (trade.position_size * 0.70)
            )
        else:
            tp1_pnl = (
                (trade.entry_price - trade.tp1_price) /
                trade.entry_price * (trade.position_size * 0.70)
            )

        # Deduct fees on 70%
        fee = (trade.position_size * 0.70) * TAKER_FEE * 2
        tp1_pnl = round(tp1_pnl - fee, 4)

        # Record partial PnL to daily risk NOW
        # So dashboard shows it immediately
        state_manager.record_partial_pnl(tp1_pnl)

        log.info(
            f"TP1 hit: {trade.coin} "
            f"partial_pnl:${tp1_pnl} "
            f"BE SL placed @ {trade.entry_price}"
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


    # ═══════════════════════════════════════════════════
    # CLOSE TRADE
    # phase=1 → full position
    # phase=2 → 30% remaining (70% already at TP1)
    # ═══════════════════════════════════════════════════
    async def _close_trade(
        self,
        trade:        Trade,
        exit_price:   float,
        outcome:      str,
        close_reason: str,
        phase:        int = 1
    ):
        _, qty_tp2 = self._parse_quantities(trade)

        # ── ACCURATE PNL ──
        if phase == 1:
            # Full position — no TP1 hit
            active_size = trade.position_size
        else:
            # Phase 2 — only 30% remaining
            # 70% already captured at TP1
            active_size = trade.position_size * 0.30

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

        # Fees on remaining position
        fee     = active_size * TAKER_FEE * 2
        pnl     = round(gross_pnl - fee, 4)

        # If phase 2 — add the TP1 partial PnL
        # that was already recorded
        # Total PnL = TP1 partial + TP2/BE close
        # We store final close PnL only for the remainder
        # Daily risk already has TP1 partial from
        # record_partial_pnl() call in _handle_tp1_hit

        # Update trade in DB
        db = SessionLocal()
        try:
            t              = db.query(Trade).filter(
                Trade.id == trade.id
            ).first()
            t.state        = TradeState.EXIT
            t.is_active    = False
            t.outcome      = outcome
            t.exit_price   = exit_price
            t.pnl          = pnl
            t.close_reason = close_reason
            t.closed_at    = datetime.utcnow()
            db.commit()

            # Update linked signal
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

        # Record to daily risk
        state_manager.record_trade_close(pnl)

        # Set idle
        state_manager.set_idle()

        await self._send_close_alert(
            trade, exit_price, pnl, outcome, close_reason
        )

        log.info(
            f"Trade closed: {trade.coin} {outcome} "
            f"phase:{phase} "
            f"PnL:${pnl} "
            f"Reason:{close_reason}"
        )


    # ═══════════════════════════════════════════════════
    # MANUAL CLOSE
    # ═══════════════════════════════════════════════════
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

        # Cancel all open orders
        for oid in [
            trade.sl_order_id,
            trade.tp1_order_id,
            trade.tp2_order_id
        ]:
            if oid:
                cancel_order(trade.coin, oid)

        # Determine remaining quantity
        tp1_hit  = self._is_tp1_already_hit(trade)
        _, qty_tp2 = self._parse_quantities(trade)

        qty = calculate_quantity(
            coin     = trade.coin,
            pos_size = trade.position_size * (0.30 if tp1_hit else 1.0),
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
        phase         = 2 if tp1_hit else 1

        await self._close_trade(
            trade        = trade,
            exit_price   = current_price,
            outcome      = "manual",
            close_reason = "MANUAL",
            phase        = phase
        )

        return {"success": True, "reason": "Trade closed manually"}


    # ═══════════════════════════════════════════════════
    # ABORT TRADE
    # ═══════════════════════════════════════════════════
    async def _abort_trade(self, trade: Trade, reason: str):
        db = SessionLocal()
        try:
            t = db.query(Trade).filter(
                Trade.id == trade.id
            ).first()
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


    # ═══════════════════════════════════════════════════
    # PARSE QUANTITIES FROM NOTES
    # ═══════════════════════════════════════════════════
    def _parse_quantities(
        self, trade: Trade
    ) -> tuple:
        """Returns (qty_tp1, qty_tp2)"""
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
            pass
        # Fallback — estimate from position
        total = trade.position_size or 0
        price = trade.entry_price or 1
        qty   = total / price
        return round(qty * 0.70, 3), round(qty * 0.30, 3)


    # ═══════════════════════════════════════════════════
    # TELEGRAM ALERTS
    # ═══════════════════════════════════════════════════
    async def _send_entry_alert(self, trade, signal, sizing):
        emoji     = "🏆" if trade.grade == "A+" else "✅"
        dir_emoji = "📈" if trade.direction == "LONG" else "📉"
        await send(
            f"{emoji} *Grade {trade.grade} — TRADE OPENED*\n\n"
            f"{dir_emoji} *{trade.coin}USDT {trade.direction}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Entry:  `{trade.entry_price}`\n"
            f"SL:     `{trade.sl_price}`\n"
            f"TP1:    `{trade.tp1_price}` (70%)\n"
            f"TP2:    `{trade.tp2_price}` (30%)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Risk:   `${sizing['risk_amt']}`\n"
            f"Size:   `${sizing['pos_size']}`\n"
            f"Lev:    `{cfg.LEVERAGE}x`\n\n"
            f"Type /status to monitor"
        )

    async def _send_close_alert(
        self, trade, exit_price, pnl, outcome, close_reason
    ):
        emoji     = (
            "✅" if outcome == "win"   else
            "❌" if outcome == "loss"  else
            "⏹"
        )
        pnl_emoji = "📈" if pnl >= 0 else "📉"
        await send(
            f"{emoji} *Trade Closed — {close_reason}*\n\n"
            f"*{trade.coin}USDT {trade.direction}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Entry:   `{trade.entry_price}`\n"
            f"Exit:    `{exit_price}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{pnl_emoji} PnL:    `${pnl}`\n"
            f"Outcome: `{outcome.upper()}`\n\n"
            f"Bot idle — scanning for next signal\n"
            f"Type /pnl for full stats"
        )


# ── GLOBAL INSTANCE ──
trade_manager = TradeManager()