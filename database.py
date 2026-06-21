import os
from contextlib import contextmanager
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, Integer,
    String, Float, DateTime, Text, Boolean, BigInteger, event
)
from sqlalchemy.orm import declarative_base, sessionmaker

os.makedirs("database", exist_ok=True)

Base = declarative_base()
engine = create_engine(
    "sqlite:///database/signals.db",
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_size=5,
    max_overflow=10
)

@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def get_session():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Signal(Base):
    __tablename__ = "signals"

    id             = Column(Integer, primary_key=True)
    timestamp      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    coin           = Column(String)
    direction      = Column(String)
    grade          = Column(String)
    score          = Column(Float)
    signal_type    = Column(String)
    entry          = Column(Float)
    sl             = Column(Float)
    tp1            = Column(Float)
    tp2            = Column(Float)
    sl_pct         = Column(Float)
    risk_amt       = Column(Float)
    risk_pct       = Column(Float)
    position       = Column(Float)
    leverage       = Column(String)
    regime         = Column(String)
    session        = Column(String)
    sweep_score    = Column(Float)
    retest_score   = Column(Float)
    disp_score     = Column(Float)
    funding        = Column(Float)
    oi_signal      = Column(String)
    outcome        = Column(String, default="pending")
    exit_price     = Column(Float, nullable=True)
    pnl            = Column(Float, nullable=True)
    notes          = Column(Text, nullable=True)
    factor_scores  = Column(Text, nullable=True)
    market_score   = Column(Float, nullable=True)
    entry_score    = Column(Float, nullable=True)
    atr_at_entry   = Column(Float, nullable=True)
    btc_score      = Column(Float, nullable=True)


class Candle(Base):
    __tablename__ = "candles"

    id        = Column(Integer, primary_key=True)
    coin      = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    open      = Column(Float)
    high      = Column(Float)
    low       = Column(Float)
    close     = Column(Float)
    volume    = Column(Float)


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id            = Column(Integer, primary_key=True)
    run_at        = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    coin          = Column(String)
    timeframe     = Column(String)
    period_start  = Column(String)
    period_end    = Column(String)
    total_signals = Column(Integer)
    aplus_signals = Column(Integer)
    a_signals     = Column(Integer)
    total_trades  = Column(Integer)
    wins          = Column(Integer)
    losses        = Column(Integer)
    win_rate      = Column(Float)
    total_pnl     = Column(Float)
    max_drawdown  = Column(Float)
    best_trade    = Column(Float)
    worst_trade   = Column(Float)
    avg_trade     = Column(Float)
    notes         = Column(Text, nullable=True)


class CoinConfig(Base):
    __tablename__ = "coin_config"

    id              = Column(Integer, primary_key=True)
    coin            = Column(String, unique=True, nullable=False)
    enabled         = Column(Boolean, default=True)
    tier            = Column(Integer, default=1)
    source          = Column(String, default="manual")
    volume_24h      = Column(Float, nullable=True)
    added_at        = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen       = Column(DateTime, nullable=True)
    btc_correlation = Column(Float, default=0.8, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id        = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    action    = Column(String)
    source    = Column(String)
    detail    = Column(Text, nullable=True)
    ip        = Column(String, nullable=True)
    success   = Column(Boolean, default=True)


def init_db():
    Base.metadata.create_all(engine)
    import logging
    logging.getLogger(__name__).info("Database tables created")


init_db()