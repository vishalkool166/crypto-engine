import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


async def reconcile_on_startup() -> None:
    try:
        from trade.exchange import get_positions
        from database import SessionLocal, Trade as TradeModel
        from trade.exchange import get_symbol_precision, place_algo_order

        positions = await get_positions()
        if not positions:
            log.info("Reconciler: no open positions on exchange")
            return

        pos_map = {
            p["symbol"].replace("USDT", ""): p
            for p in positions
            if float(p.get("positionAmt", 0)) != 0
        }

        log.info("Reconciler: found %s open positions on exchange", len(pos_map))

        with SessionLocal() as db:
            pending = db.query(TradeModel).filter(
                TradeModel.state   == "pending",
                TradeModel.outcome == "pending",
            ).all()

            active = db.query(TradeModel).filter(
                TradeModel.is_active == True
            ).all()

        active_coins  = {t.coin for t in active}
        pending_coins = {t.coin: t for t in pending}

        for coin, pos in pos_map.items():
            amt        = float(pos.get("positionAmt", 0))
            entry      = float(pos.get("entryPrice",  0))
            is_long    = amt > 0
            direction  = "LONG" if is_long else "SHORT"

            if coin in active_coins:
                log.info("Reconciler: %s already active in DB — skipping", coin)
                continue

            if coin in pending_coins:
                trade = pending_coins[coin]
                log.info(
                    "Reconciler: %s pending trade found — activating (entry=%.4f)",
                    coin, entry
                )
                await _activate_pending_trade(trade, entry, pos)
            else:
                log.warning(
                    "Reconciler: %s has position on exchange but NO trade in DB — orphan position",
                    coin
                )
                await _handle_orphan_position(coin, direction, entry, pos)

    except Exception as e:
        log.error("reconcile_on_startup: %s", e)


async def _activate_pending_trade(trade, fill_price: float, pos: dict) -> None:
    try:
        from database import SessionLocal, Trade as TradeModel
        from trade.exchange import place_algo_order, get_symbol_precision

        coin      = trade.coin
        symbol    = f"{coin}USDT"
        direction = trade.direction
        is_long   = direction == "LONG"
        sl_side   = "BUY"  if not is_long else "SELL"
        tp_side   = "BUY"  if not is_long else "SELL"

        prec = await get_symbol_precision(symbol)
        pp   = prec["price_precision"]

        sl  = float(trade.sl_price  or 0)
        tp1 = float(trade.tp1_price or 0)

        sl_oid  = None
        tp1_oid = None

        if sl > 0:
            try:
                sl_order = await place_algo_order(
                    symbol         = symbol,
                    side           = sl_side,
                    order_type     = "STOP_MARKET",
                    trigger_price  = sl,
                    price_precision= pp,
                    close_position = True,
                )
                sl_oid = str(sl_order.get("algoId", ""))
                log.info("Reconciler: SL placed for %s at %.4f algoId=%s", coin, sl, sl_oid)
            except Exception as e:
                log.warning("Reconciler: SL placement failed for %s: %s", coin, e)

        if tp1 > 0:
            try:
                tp_order = await place_algo_order(
                    symbol         = symbol,
                    side           = tp_side,
                    order_type     = "TAKE_PROFIT_MARKET",
                    trigger_price  = tp1,
                    price_precision= pp,
                    close_position = True,
                )
                tp1_oid = str(tp_order.get("algoId", ""))
                log.info("Reconciler: TP placed for %s at %.4f algoId=%s", coin, tp1, tp1_oid)
            except Exception as e:
                log.warning("Reconciler: TP placement failed for %s: %s", coin, e)

        amt    = abs(float(pos.get("positionAmt", 0)))
        margin = fill_price * amt / 5

        with SessionLocal() as db:
            t = db.query(TradeModel).filter(TradeModel.id == trade.id).first()
            if t:
                t.state        = "open"
                t.is_active    = True
                t.entry_price  = fill_price
                t.margin_used  = round(margin, 4)
                t.sl_order_id  = sl_oid
                t.tp1_order_id = tp1_oid
                t.opened_at    = datetime.now(timezone.utc)

        log.info(
            "Reconciler: trade #%s %s %s activated — entry=%.4f sl=%s tp=%s",
            trade.id, coin, direction, fill_price, sl_oid, tp1_oid
        )

        from alerts.telegram import send
        await send(
            f"🔄 *Startup Reconciliation*\n\n"
            f"Found unfilled trade #{trade.id} {coin} {direction}\n"
            f"Position was open on exchange — activated\n"
            f"Entry: `{fill_price:.4f}`\n"
            f"SL: `{sl:.4f}` {'✅' if sl_oid else '⚠️ failed'}\n"
            f"TP: `{tp1:.4f}` {'✅' if tp1_oid else '⚠️ failed'}"
        )

    except Exception as e:
        log.error("_activate_pending_trade %s: %s", trade.coin, e)


async def _handle_orphan_position(
    coin:      str,
    direction: str,
    entry:     float,
    pos:       dict,
) -> None:
    try:
        from alerts.telegram import send
        amt = float(pos.get("positionAmt", 0))
        log.warning(
            "Reconciler: orphan position %s %s amt=%s entry=%.4f — no DB record",
            coin, direction, amt, entry
        )
        await send(
            f"⚠️ *Orphan Position Detected*\n\n"
            f"Coin: `{coin}` {direction}\n"
            f"Amount: `{amt}`\n"
            f"Entry: `{entry:.4f}`\n\n"
            f"_No trade record found in DB._\n"
            f"_Please close manually on Binance._"
        )
    except Exception as e:
        log.error("_handle_orphan_position %s: %s", coin, e)