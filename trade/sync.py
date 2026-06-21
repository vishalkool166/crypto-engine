import logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)


async def sync_freqtrade_outcomes() -> dict:
    """
    Reads closed trades from Freqtrade API.
    Matches them to Signal table records.
    Updates Signal.outcome, Signal.pnl, Signal.exit_price.
    Returns sync report.
    """
    try:
        from api.freqtrade import _ft_get
        from database import SessionLocal, Signal as SignalModel

        data = await _ft_get("/trades?limit=100")
        if not data:
            log.warning("No trade data from Freqtrade")
            return {"synced": 0, "unmatched": 0, "error": "No data"}

        trades = data.get("trades", [])
        if not trades:
            log.info("No closed trades in Freqtrade yet")
            return {"synced": 0, "unmatched": 0}

        closed_trades = [
            t for t in trades
            if not t.get("is_open", True)
        ]

        if not closed_trades:
            log.info("No closed trades to sync")
            return {"synced": 0, "unmatched": 0}

        log.info(f"Syncing {len(closed_trades)} closed Freqtrade trades")

        synced    = 0
        unmatched = 0
        skipped   = 0

        with SessionLocal() as db:
            for ft_trade in closed_trades:
                try:
                    pair       = ft_trade.get("pair", "")
                    coin       = pair.replace("/USDT:USDT", "").replace("/USDT", "")
                    open_rate  = float(ft_trade.get("open_rate", 0))
                    close_rate = float(ft_trade.get("close_rate", 0))
                    profit_abs = float(ft_trade.get("profit_abs", 0))
                    is_short   = ft_trade.get("is_short", False)
                    direction  = "SHORT" if is_short else "LONG"

                    open_date_str = ft_trade.get("open_date", "")
                    try:
                        open_dt = datetime.fromisoformat(
                            open_date_str.replace("Z", "+00:00")
                        )
                    except Exception:
                        open_dt = None

                    existing = db.query(SignalModel).filter(
                        SignalModel.coin      == coin,
                        SignalModel.direction == direction,
                        SignalModel.outcome   == "pending"
                    ).all()

                    if not existing:
                        unmatched += 1
                        log.debug(f"No pending signal found for {coin} {direction}")
                        continue

                    best_match = None
                    best_score = float("inf")

                    for sig in existing:
                        if not sig.entry:
                            continue

                        price_diff = abs(sig.entry - open_rate) / open_rate

                        if price_diff > 0.02:
                            continue

                        time_score = 0
                        if open_dt and sig.timestamp:
                            sig_ts = sig.timestamp
                            if sig_ts.tzinfo is None:
                                sig_ts = sig_ts.replace(tzinfo=timezone.utc)
                            time_diff = abs((open_dt - sig_ts).total_seconds())
                            time_score = time_diff
                        else:
                            time_score = price_diff * 10000

                        combined = price_diff * 1000 + time_score / 3600

                        if combined < best_score:
                            best_score = combined
                            best_match = sig

                    if not best_match:
                        unmatched += 1
                        log.debug(f"No price match for {coin} {direction} entry:{open_rate}")
                        continue

                    if best_match.outcome != "pending":
                        skipped += 1
                        continue

                    outcome = "win" if profit_abs > 0 else "loss"

                    best_match.outcome    = outcome
                    best_match.pnl        = round(profit_abs, 6)
                    best_match.exit_price = close_rate

                    db.commit()
                    synced += 1

                    log.info(
                        f"Synced: {coin} {direction} "
                        f"entry:{open_rate} exit:{close_rate} "
                        f"pnl:{profit_abs:.4f} outcome:{outcome} "
                        f"signal_id:{best_match.id}"
                    )

                except Exception as e:
                    log.error(f"Error syncing trade {ft_trade.get('trade_id')}: {e}")
                    continue

        result = {
            "synced":    synced,
            "unmatched": unmatched,
            "skipped":   skipped,
            "total":     len(closed_trades)
        }

        log.info(f"Sync complete: {result}")
        return result

    except Exception as e:
        log.error(f"sync_freqtrade_outcomes error: {e}")
        return {"synced": 0, "unmatched": 0, "error": str(e)}


async def get_sync_status() -> dict:
    """Returns current sync status for health endpoint."""
    try:
        from database import SessionLocal, Signal as SignalModel

        with SessionLocal() as db:
            total   = db.query(SignalModel).count()
            pending = db.query(SignalModel).filter(
                SignalModel.outcome == "pending"
            ).count()
            closed  = db.query(SignalModel).filter(
                SignalModel.outcome.in_(["win", "loss"])
            ).count()
            wins    = db.query(SignalModel).filter(
                SignalModel.outcome == "win"
            ).count()

        win_rate = round(wins / closed * 100, 1) if closed > 0 else 0

        return {
            "total_signals":   total,
            "pending_signals": pending,
            "closed_signals":  closed,
            "wins":            wins,
            "losses":          closed - wins,
            "win_rate":        win_rate,
            "sync_needed":     pending > 0
        }

    except Exception as e:
        log.error(f"get_sync_status error: {e}")
        return {}