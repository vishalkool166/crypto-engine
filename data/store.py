import pandas as pd
import logging
from database import SessionLocal, Candle
from sqlalchemy import and_
from config import cfg

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# SAVE CANDLES
# ═══════════════════════════════════════════════════════
def save_candles(
    coin:      str,
    timeframe: str,
    df:        pd.DataFrame
):
    """
    Saves DataFrame of candles to DB.
    Skips duplicates by timestamp.
    """
    if df is None or df.empty:
        return

    db = SessionLocal()
    try:
        # Get existing timestamps
        existing = set(
            row.timestamp for row in
            db.query(Candle.timestamp).filter(
                and_(
                    Candle.coin      == coin,
                    Candle.timeframe == timeframe
                )
            ).all()
        )

        new_rows = []
        for ts, row in df.iterrows():
            # Convert timestamp to unix ms
            ts_ms = int(
                pd.Timestamp(ts).timestamp() * 1000
            )
            if ts_ms in existing:
                continue
            new_rows.append(Candle(
                coin      = coin,
                timeframe = timeframe,
                timestamp = ts_ms,
                open      = float(row["open"]),
                high      = float(row["high"]),
                low       = float(row["low"]),
                close     = float(row["close"]),
                volume    = float(row["volume"])
            ))

        if new_rows:
            db.bulk_save_objects(new_rows)
            db.commit()
            log.info(
                f"Saved {len(new_rows)} new candles: "
                f"{coin} {timeframe}"
            )

    except Exception as e:
        log.error(f"Save candles error {coin} {timeframe}: {e}")
        db.rollback()
    finally:
        db.close()


# ═══════════════════════════════════════════════════════
# LOAD CANDLES
# ═══════════════════════════════════════════════════════
def load_candles(
    coin:      str,
    timeframe: str,
    limit:     int = 1000
) -> pd.DataFrame:
    """
    Loads candles from DB as DataFrame.
    Returns None if not enough data.
    """
    db = SessionLocal()
    try:
        rows = db.query(Candle).filter(
            and_(
                Candle.coin      == coin,
                Candle.timeframe == timeframe
            )
        ).order_by(
            Candle.timestamp.desc()
        ).limit(limit).all()

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
        log.error(f"Load candles error {coin} {timeframe}: {e}")
        return None
    finally:
        db.close()


# ═══════════════════════════════════════════════════════
# GET LAST TIMESTAMP
# used for incremental fetch
# ═══════════════════════════════════════════════════════
def get_last_timestamp(
    coin:      str,
    timeframe: str
) -> int:
    """
    Returns last stored candle timestamp in unix ms.
    Returns None if no data stored yet.
    """
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
        log.error(f"Get last ts error: {e}")
        return None
    finally:
        db.close()


# ═══════════════════════════════════════════════════════
# HAS ENOUGH DATA
# ═══════════════════════════════════════════════════════
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
        log.error(f"Has enough data error: {e}")
        return False
    finally:
        db.close()


# ═══════════════════════════════════════════════════════
# GET CANDLE COUNT
# ═══════════════════════════════════════════════════════
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
        log.error(f"Count error: {e}")
        return 0
    finally:
        db.close()