import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


async def sync_freqtrade_outcomes() -> dict:
    try:
        from api.freqtrade import _ft_get
        from database import SessionLocal, Signal as SignalModel

        data = await _ft_get("/trades?limit=100")

        if not data:
            log.warning("No trade data from Freqtrade")
            return {"synced": 0, "unmatched": 0, "error": "No data"}

        if isinstance(data, list):
            all_trades = data
        elif isinstance(data, dict):
            all_trades = data.get("trades", [])
        else:
            all_trades = []

        if not all_trades:
            log.info("No trades in Freqtrade yet")
            return {"synced": 0, "unmatched": 0, "total": 0}

        closed_trades = [
            t for t in all_trades
            if not t.get("is_open", True) and t.get("close_rate")
        ]

        if not closed_trades:
            log.info("No closed trades to sync")
            return {"synced": 0, "unmatched": 0, "total": 0}

        log.info(f"Found {len(closed_trades)} closed trades to sync")

        synced    = 0
        unmatched = 0
        skipped   = 0

        with SessionLocal() as db:
            for ft_trade in closed_trades:
                try:
                    pair       = ft_trade.get("pair", "")
                    coin       = pair.replace("/USDT:USDT", "").replace("/USDT", "")
                    open_rate  = float(ft_trade.get("open_rate",  0))
                    close_rate = float(ft_trade.get("close_rate", 0))
                    profit_abs = float(ft_trade.get("profit_abs", 0))
                    is_short   = ft_trade.get("is_short", False)
                    direction  = "SHORT" if is_short else "LONG"
                    trade_id   = ft_trade.get("trade_id")

                    log.info(
                        f"Processing: {coin} {direction} "
                        f"entry:{open_rate} exit:{close_rate} "
                        f"pnl:{profit_abs} trade_id:{trade_id}"
                    )

                    open_date_str = ft_trade.get("open_date", "")
                    try:
                        open_dt = datetime.fromisoformat(
                            open_date_str.replace("Z", "+00:00")
                        )
                        if open_dt.tzinfo is None:
                            open_dt = open_dt.replace(tzinfo=timezone.utc)
                    except Exception:
                        open_dt = None

                    existing = db.query(SignalModel).filter(
                        SignalModel.coin      == coin,
                        SignalModel.direction == direction,
                        SignalModel.outcome   == "pending"
                    ).order_by(SignalModel.timestamp.desc()).all()

                    if not existing:
                        existing = db.query(SignalModel).filter(
                            SignalModel.coin    == coin,
                            SignalModel.outcome == "pending"
                        ).order_by(SignalModel.timestamp.desc()).all()

                    if not existing:
                        unmatched += 1
                        log.warning(
                            f"No pending signal for {coin} {direction} "
                            f"trade_id:{trade_id}"
                        )
                        continue

                    best_match = None

                    if open_dt:
                        best_score = float("inf")
                        for sig in existing:
                            if not sig.timestamp:
                                continue
                            sig_ts = sig.timestamp
                            if sig_ts.tzinfo is None:
                                sig_ts = sig_ts.replace(tzinfo=timezone.utc)
                            if sig_ts > open_dt:
                                continue
                            time_diff = abs((open_dt - sig_ts).total_seconds())
                            if time_diff < best_score:
                                best_score = time_diff
                                best_match = sig

                    if not best_match and existing:
                        best_match = existing[0]
                        log.info(
                            f"Using most recent signal for {coin} "
                            f"signal_id:{best_match.id}"
                        )

                    if not best_match:
                        unmatched += 1
                        continue

                    if best_match.outcome != "pending":
                        skipped += 1
                        log.info(
                            f"Skipping already synced signal "
                            f"id:{best_match.id} outcome:{best_match.outcome}"
                        )
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
                    log.error(
                        f"Error syncing trade "
                        f"{ft_trade.get('trade_id')}: {e}"
                    )
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