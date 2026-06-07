import os
from sqlalchemy import (
    create_engine, Column, Integer,
    String, Float, DateTime, Text, Boolean, BigInteger
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

os.makedirs("database", exist_ok=True)

Base = declarative_base()
engine = create_engine(
    "sqlite:///database/signals.db",
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine)


class Signal(Base):
    __tablename__ = "signals"

    id           = Column(Integer, primary_key=True)
    timestamp    = Column(DateTime, default=datetime.utcnow)
    coin         = Column(String)
    direction    = Column(String)
    grade        = Column(String)
    score        = Column(Float)
    signal_type  = Column(String)
    entry        = Column(Float)
    sl           = Column(Float)
    tp1          = Column(Float)
    tp2          = Column(Float)
    tp3          = Column(Float)
    sl_pct       = Column(Float)
    risk_amt     = Column(Float)
    risk_pct     = Column(Float)
    position     = Column(Float)
    leverage     = Column(String)
    regime       = Column(String)
    session      = Column(String)
    sweep_score  = Column(Float)
    retest_score = Column(Float)
    disp_score   = Column(Float)
    funding      = Column(Float)
    oi_signal    = Column(String)
    outcome      = Column(String, default="pending")
    exit_price   = Column(Float, nullable=True)
    pnl          = Column(Float, nullable=True)
    notes        = Column(Text, nullable=True)


class Trade(Base):
    __tablename__ = "trades"

    id               = Column(Integer, primary_key=True)
    signal_id        = Column(Integer, nullable=True)
    coin             = Column(String)
    direction        = Column(String)
    grade            = Column(String)
    state            = Column(String, default="idle")
    is_active        = Column(Boolean, default=False)
    entry_price      = Column(Float)
    sl_price         = Column(Float)
    tp1_price        = Column(Float)
    tp2_price        = Column(Float)
    current_price    = Column(Float, nullable=True)
    entry_order_id   = Column(String, nullable=True)
    sl_order_id      = Column(String, nullable=True)
    tp1_order_id     = Column(String, nullable=True)
    tp2_order_id     = Column(String, nullable=True)
    position_size    = Column(Float)
    margin_used      = Column(Float)
    leverage         = Column(Integer)
    risk_amt         = Column(Float)
    opened_at        = Column(DateTime, default=datetime.utcnow)
    closed_at        = Column(DateTime, nullable=True)
    outcome          = Column(String, default="pending")
    exit_price       = Column(Float, nullable=True)
    pnl              = Column(Float, nullable=True)
    close_reason     = Column(String, nullable=True)
    trade_date       = Column(String)
    notes            = Column(Text, nullable=True)
    # Health state at moment of close — used by factor
    # analysis to correlate thesis health with outcome
    health_at_close  = Column(String, nullable=True)


class DailyRisk(Base):
    __tablename__ = "daily_risk"

    id           = Column(Integer, primary_key=True)
    date         = Column(String, unique=True)
    trades_taken = Column(Integer, default=0)
    total_loss   = Column(Float, default=0.0)
    total_pnl    = Column(Float, default=0.0)
    cap_hit      = Column(Boolean, default=False)


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
    run_at        = Column(DateTime, default=datetime.utcnow)
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


def init_db():
    Base.metadata.create_all(engine)
    # SQLite does not auto-add columns to existing tables.
    # If upgrading from previous version, run this once:
    # ALTER TABLE trades ADD COLUMN health_at_close TEXT;
    import logging
    logging.getLogger(__name__).info("Database tables created")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


init_db()