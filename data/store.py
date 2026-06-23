import pandas as pd
import logging
from database import SessionLocal, Candle
from sqlalchemy import and_
from config import cfg

log = logging.getLogger(__name__)


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
            log.info(f"Saved {saved} new candles: {coin} {timeframe}")

    except Exception as e:
        log.error(f"Save candles error {coin} {timeframe}: {e}")
        db.rollback()
    finally:
        db.close()


def load_candles(
    coin:      str,
    timeframe: str,
    limit:     int = 1000
) -> pd.DataFrame:
    db = SessionLocal()
    try:
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
        log.error(f"Load candles error {coin} {timeframe}: {e}")
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
        log.error(f"Get last ts error: {e}")
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
        log.error(f"Has enough data error: {e}")
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
        log.error(f"Count error: {e}")
        return 0
    finally:
        db.close()