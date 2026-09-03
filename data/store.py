import pandas as pd
import logging
from database import SessionLocal, Candle
from sqlalchemy import and_
from config import cfg

log = logging.getLogger(__name__)

CANDLE_CAPS = {
    "1w":  250,
    "1d":  250,
    "4h":  350,
    "1h":  350,
    "15m": 250,
}


def save_candles(
    coin:      str,
    timeframe: str,
    df:        pd.DataFrame
):
    if df is None or df.empty:
        return

    db = SessionLocal()
    try:
        new_rows = []
        for ts, row in df.iterrows():
            ts_ms = int(pd.Timestamp(ts).timestamp() * 1000)
            new_rows.append({
                "coin":      coin,
                "timeframe": timeframe,
                "timestamp": ts_ms,
                "open":      float(row["open"]),
                "high":      float(row["high"]),
                "low":       float(row["low"]),
                "close":     float(row["close"]),
                "volume":    float(row["volume"])
            })

        if not new_rows:
            return

        from sqlalchemy.dialects.sqlite import insert
        stmt = insert(Candle).values(new_rows)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["coin", "timeframe", "timestamp"]
        )
        result = db.execute(stmt)
        db.commit()

        saved = result.rowcount
        if saved > 0:
            log.info("Saved %s new candles: %s %s", saved, coin, timeframe)

        _purge_old_candles(coin, timeframe, db)

    except Exception as e:
        log.error("Save candles error %s %s: %s", coin, timeframe, e)
        db.rollback()
    finally:
        db.close()


def _purge_old_candles(coin: str, timeframe: str, db) -> None:
    try:
        cap = CANDLE_CAPS.get(timeframe)
        if not cap:
            return

        total = db.query(Candle).filter(
            and_(
                Candle.coin      == coin,
                Candle.timeframe == timeframe,
            )
        ).count()

        if total <= cap:
            return

        excess = total - cap

        oldest = db.query(Candle).filter(
            and_(
                Candle.coin      == coin,
                Candle.timeframe == timeframe,
            )
        ).order_by(
            Candle.timestamp.asc()
        ).limit(excess).all()

        for row in oldest:
            db.delete(row)

        db.commit()
        log.info("Purged %s old candles: %s %s (cap=%s)", excess, coin, timeframe, cap)

    except Exception as e:
        log.error("Purge candles error %s %s: %s", coin, timeframe, e)
        db.rollback()


def load_candles(
    coin:      str,
    timeframe: str,
    limit:     int = 1000
) -> pd.DataFrame:
    db = SessionLocal()
    try:
        cap   = CANDLE_CAPS.get(timeframe)
        limit = min(limit, cap) if cap else limit

        rows = db.query(Candle).filter(
            and_(
                Candle.coin      == coin,
                Candle.timeframe == timeframe,
                Candle.timestamp >= 1000000000000
            )
        ).order_by(Candle.timestamp.desc()).limit(limit).all()

        if not rows:
            return None

        data = [{
            "timestamp": pd.Timestamp(r.timestamp, unit="ms"),
            "open":      r.open,
            "high":      r.high,
            "low":       r.low,
            "close":     r.close,
            "volume":    r.volume
        } for r in reversed(rows)]

        df = pd.DataFrame(data)
        df = df.set_index("timestamp")
        return df

    except Exception as e:
        log.error("Load candles error %s %s: %s", coin, timeframe, e)
        return None
    finally:
        db.close()


def get_last_timestamp(
    coin:      str,
    timeframe: str
) -> int:
    db = SessionLocal()
    try:
        row = db.query(Candle).filter(
            and_(
                Candle.coin      == coin,
                Candle.timeframe == timeframe
            )
        ).order_by(
            Candle.timestamp.desc()
        ).first()

        return row.timestamp if row else None

    except Exception as e:
        log.error("Get last ts error: %s", e)
        return None
    finally:
        db.close()


def has_enough_data(
    coin:      str,
    timeframe: str,
    minimum:   int = 200
) -> bool:
    db = SessionLocal()
    try:
        count = db.query(Candle).filter(
            and_(
                Candle.coin      == coin,
                Candle.timeframe == timeframe
            )
        ).count()
        return count >= minimum
    except Exception as e:
        log.error("Has enough data error: %s", e)
        return False
    finally:
        db.close()


def get_candle_count(
    coin:      str,
    timeframe: str
) -> int:
    db = SessionLocal()
    try:
        return db.query(Candle).filter(
            and_(
                Candle.coin      == coin,
                Candle.timeframe == timeframe
            )
        ).count()
    except Exception as e:
        log.error("Count error: %s", e)
        return 0
    finally:
        db.close()


def purge_all_beyond_caps() -> dict:
    results = {}
    try:
        from database import SessionLocal, Candle
        from sqlalchemy import distinct

        with SessionLocal() as db:
            pairs = db.query(
                distinct(Candle.coin),
                Candle.timeframe
            ).all()

        total_purged = 0
        for coin, timeframe in pairs:
            cap = CANDLE_CAPS.get(timeframe)
            if not cap:
                continue

            with SessionLocal() as db:
                total = db.query(Candle).filter(
                    and_(
                        Candle.coin      == coin,
                        Candle.timeframe == timeframe,
                    )
                ).count()

                if total <= cap:
                    continue

                excess = total - cap

                oldest = db.query(Candle).filter(
                    and_(
                        Candle.coin      == coin,
                        Candle.timeframe == timeframe,
                    )
                ).order_by(
                    Candle.timestamp.asc()
                ).limit(excess).all()

                for row in oldest:
                    db.delete(row)

                db.commit()
                total_purged += excess
                results[f"{coin}_{timeframe}"] = excess
                log.info("Purged %s candles: %s %s", excess, coin, timeframe)

        log.info("Total purged: %s candles across %s pairs", total_purged, len(results))
        results["total"] = total_purged
        return results

    except Exception as e:
        log.error("purge_all_beyond_caps error: %s", e)
        return {"error": str(e)}