import logging
from datetime import datetime, timezone
from alerts.telegram import send, now_ist
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
from alerts.telegram import send
from config import cfg

log = logging.getLogger(__name__)

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

        log.info(
            f"open_trade called: "
            f"{signal.get('coin')} "
            f"{signal.get('direction')} "
            f"Grade:{signal.get('grade')} "
            f"Score:{signal.get('score')}"
        )

        if not state_manager.is_idle:
            trade = state_manager.current_trade
            log.info(
                f"Already in trade: "
                f"{trade.coin if trade else 'unknown'} — signal ignored"
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

        log.info(
            f"Sizing approved: "
            f"risk:${sizing['risk_amt']} "
            f"pos:${sizing['pos_size']} "
            f"margin:${sizing['margin']}"
        )

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
            await self._abort_trade(trade, "SL order failed — position closed")
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

    # ═══════════════════════════════════════════════════
    # MONITOR TRADE
    # Checks order status and runs health engine.
    # Health engine informs only — never auto-closes.
    # ═══════════════════════════════════════════════════
    async def monitor_trade(self):
        if state_manager.is_idle:
            return

        trade_id = state_manager.current_trade.id

        db = SessionLocal()
        try:
            trade = db.query(Trade).filter(
                Trade.id == trade_id
            ).first()

            if not trade or not trade.is_active:
                state_manager.set_idle()
                return

            t_id            = trade.id
            t_coin          = trade.coin
            t_direction     = trade.direction
            t_entry_price   = trade.entry_price
            t_sl_price      = trade.sl_price
            t_tp1_price     = trade.tp1_price
            t_tp2_price     = trade.tp2_price
            t_position_size = trade.position_size
            t_sl_order_id   = trade.sl_order_id
            t_tp1_order_id  = trade.tp1_order_id
            t_tp2_order_id  = trade.tp2_order_id
            t_notes         = trade.notes

        finally:
            db.close()

        current_price = get_current_price(t_coin)
        if not current_price:
            log.warning(f"Could not get price: {t_coin}")
            return

        db = SessionLocal()
        try:
            t = db.query(Trade).filter(Trade.id == t_id).first()
            if t:
                t.current_price = current_price
                db.commit()
        finally:
            db.close()

        tp1_already_hit = (
            abs(t_sl_price - t_entry_price) / t_entry_price < 0.001
            if t_sl_price and t_entry_price
            else False
        )

        log.info(
            f"MONITOR [{t_coin}] "
            f"phase:{'2-RF' if tp1_already_hit else '1'} "
            f"current:{current_price} "
            f"entry:{t_entry_price} "
            f"sl:{t_sl_price} "
            f"tp1:{t_tp1_price} "
            f"tp2:{t_tp2_price} "
            f"sl_id:{t_sl_order_id} "
            f"tp1_id:{t_tp1_order_id} "
            f"tp2_id:{t_tp2_order_id}"
        )

        if not t_sl_order_id:
            log.warning(f"SL order ID missing for {t_coin} — trade unprotected!")
        if not t_tp1_order_id and not tp1_already_hit:
            log.warning(f"TP1 order ID missing for {t_coin}")

        db = SessionLocal()
        try:
            trade_obj = db.query(Trade).filter(Trade.id == t_id).first()
        finally:
            db.close()

        # ── RUN HEALTH ENGINE ──
        await self._run_health_check(
            trade_obj     = trade_obj,
            current_price = current_price
        )

        if not tp1_already_hit:
            if t_sl_order_id:
                sl_status = get_order_status(t_coin, str(t_sl_order_id))
                log.info(f"SL status: {sl_status}")
                if sl_status and sl_status["status"] == "closed":
                    log.info(f"SL hit: {t_coin} @ {current_price}")
                    await self._close_trade(
                        trade        = trade_obj,
                        exit_price   = current_price,
                        outcome      = "loss",
                        close_reason = "SL",
                        phase        = 1
                    )
                    return

            if t_tp1_order_id:
                tp1_status = get_order_status(t_coin, str(t_tp1_order_id))
                log.info(f"TP1 status: {tp1_status}")
                if tp1_status and tp1_status["status"] == "closed":
                    log.info(f"TP1 hit: {t_coin} @ {current_price}")
                    await self._handle_tp1_hit(trade_obj, current_price)
                    return

        else:
            if t_sl_order_id:
                sl_status = get_order_status(t_coin, str(t_sl_order_id))
                log.info(f"BE SL status: {sl_status}")
                if sl_status and sl_status["status"] == "closed":
                    log.info(f"BE SL hit: {t_coin} — closing at breakeven")
                    await self._close_trade(
                        trade        = trade_obj,
                        exit_price   = t_entry_price,
                        outcome      = "win",
                        close_reason = "TP1 + BE",
                        phase        = 2
                    )
                    return

            if t_tp2_order_id:
                tp2_status = get_order_status(t_coin, str(t_tp2_order_id))
                log.info(f"TP2 status: {tp2_status}")
                if tp2_status and tp2_status["status"] == "closed":
                    log.info(f"TP2 hit: {t_coin} @ {current_price}")
                    await self._close_trade(
                        trade        = trade_obj,
                        exit_price   = current_price,
                        outcome      = "win",
                        close_reason = "TP2",
                        phase        = 2
                    )
                    return

    # ═══════════════════════════════════════════════════
    # RUN HEALTH CHECK
    # Pulls latest market data and runs health engine.
    # Sends Telegram alert only on state change.
    # Never auto-closes — informs only.
    # ═══════════════════════════════════════════════════
    async def _run_health_check(
        self,
        trade_obj:     Trade,
        current_price: float
    ):
        try:
            from data.cache import cache
            from engines.indicators import calculate_all
            from engines.health import check_trade_health, format_health_alert

            coin = trade_obj.coin

            # Use cached scan data — avoid extra API calls
            cached = cache.get(f"signal_{coin}")
            if not cached:
                return

            d1d       = cached.get("d1d", {})
            d4h       = cached.get("d4h", {})
            retest    = cached.get("retest", {})
            sweep     = cached.get("sweep", {})
            oi_matrix = cached.get("wconf", {})

            btc_cached = cache.get("btc_1d_data")
            btc_data   = btc_cached if btc_cached else None

            explanation      = cached.get("explanation", {})
            original_thesis  = explanation.get("thesis", "")

            health = check_trade_health(
                trade            = trade_obj,
                current_price    = current_price,
                d1d              = d1d,
                d4h              = d4h,
                btc_data         = btc_data,
                oi_matrix        = oi_matrix,
                retest           = retest,
                sweep            = sweep,
                original_thesis  = original_thesis
            )

            prev_state = state_manager.health_state
            state_manager.update_health(health)

            # Send alert only on state change
            if health["state"] != prev_state:
                alert = format_health_alert(health, coin)
                await send(alert)
                log.info(
                    f"Health state changed: "
                    f"{prev_state} → {health['state']} "
                    f"for {coin}"
                )

        except Exception as e:
            log.debug(f"Health check error: {e}")

    # ═══════════════════════════════════════════════════
    # IS TP1 ALREADY HIT
    # ═══════════════════════════════════════════════════
    def _is_tp1_already_hit(self, trade: Trade) -> bool:
        if not trade.sl_price or not trade.entry_price:
            return False
        return (
            abs(trade.sl_price - trade.entry_price) /
            trade.entry_price < 0.001
        )

    # ═══════════════════════════════════════════════════
    # HANDLE TP1 HIT
    # ═══════════════════════════════════════════════════
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

        fee     = (trade.position_size * 0.70) * TAKER_FEE * 2
        tp1_pnl = round(tp1_pnl - fee, 4)

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

        fee = active_size * TAKER_FEE * 2
        pnl = round(gross_pnl - fee, 4)

        db = SessionLocal()
        try:
            t              = db.query(Trade).filter(Trade.id == trade.id).first()
            t.state        = TradeState.EXIT
            t.is_active    = False
            t.outcome      = outcome
            t.exit_price   = exit_price
            t.pnl          = pnl
            t.close_reason = close_reason
            t.closed_at    = datetime.now(timezone.utc)
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

        await self._send_close_alert(
            trade, exit_price, pnl, outcome, close_reason
        )

        log.info(
            f"Trade closed: {trade.coin} "
            f"{outcome} phase:{phase} "
            f"PnL:${pnl} Reason:{close_reason}"
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
            trade = db.query(Trade).filter(Trade.id == trade_id).first()
        finally:
            db.close()

        if not trade:
            return {"success": False, "reason": "Trade not found"}

        for oid in [trade.sl_order_id, trade.tp1_order_id, trade.tp2_order_id]:
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

    # ═══════════════════════════════════════════════════
    # PARSE QUANTITIES
    # ═══════════════════════════════════════════════════
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
            pass

        total = trade.position_size or 0
        price = trade.entry_price or 1
        qty   = total / price
        return (round(qty * 0.70, 3), round(qty * 0.30, 3))

    # ═══════════════════════════════════════════════════
    # TELEGRAM ALERTS
    # Includes thesis from explanation on entry.
    # ═══════════════════════════════════════════════════
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

        utc_now = now_ist()

        await send(
            f"{emoji} *Grade {trade.grade} — TRADE OPENED*\n\n"
            f"{dir_emoji} *{trade.coin}USDT {trade.direction}*\n"
            f"{conf_block}"
            f"Time: `{utc_now}`\n"
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
        utc_now   = now_ist()

        tv_4h = (
            f"https://www.tradingview.com/chart/"
            f"?symbol=BINANCE:{trade.coin}USDT&interval=240"
        )

        await send(
            f"{emoji} *Trade Closed — {close_reason}*\n\n"
            f"*{trade.coin}USDT {trade.direction}*\n"
            f"Time: `{utc_now}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Entry:   `{trade.entry_price}`\n"
            f"Exit:    `{exit_price}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{pnl_emoji} PnL:    `${pnl}`\n"
            f"Outcome: `{outcome.upper()}`\n\n"
            f"📊 [4H Chart]({tv_4h})\n\n"
            f"Bot idle — scanning for next signal\n"
            f"Type /pnl for full stats"
        )


trade_manager = TradeManager()