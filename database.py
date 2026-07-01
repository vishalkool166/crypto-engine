import os
from contextlib import contextmanager
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, Integer,
    String, Float, DateTime, Text, Boolean, BigInteger, event,
    UniqueConstraint
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
    cursor.execute("PRAGMA foreign_keys=ON")
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


class Trade(Base):
    __tablename__ = "trades"

    id                     = Column(Integer, primary_key=True)
    signal_id              = Column(Integer, nullable=True)
    coin                   = Column(String)
    direction              = Column(String)
    grade                  = Column(String)
    state                  = Column(String, default="idle")
    is_active              = Column(Boolean, default=False)
    entry_price            = Column(Float, nullable=True)
    sl_price               = Column(Float, nullable=True)
    tp1_price              = Column(Float, nullable=True)
    tp2_price              = Column(Float, nullable=True)
    current_price          = Column(Float, nullable=True)
    entry_order_id         = Column(String, nullable=True)
    sl_order_id            = Column(String, nullable=True)
    tp1_order_id           = Column(String, nullable=True)
    tp2_order_id           = Column(String, nullable=True)
    position_size          = Column(Float, nullable=True)
    margin_used            = Column(Float, nullable=True)
    leverage               = Column(Integer, nullable=True)
    risk_amt               = Column(Float, nullable=True)
    opened_at              = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    closed_at              = Column(DateTime, nullable=True)
    outcome                = Column(String, default="pending")
    exit_price             = Column(Float, nullable=True)
    pnl                    = Column(Float, nullable=True)
    close_reason           = Column(String, nullable=True)
    trade_date             = Column(String, nullable=True)
    notes                  = Column(Text, nullable=True)
    health_at_close        = Column(String, nullable=True)
    tp1_hit                = Column(Boolean, default=False)
    partial_pnl            = Column(Float, nullable=True)
    regime_at_entry        = Column(String, nullable=True)
    session_at_entry       = Column(String, nullable=True)
    score_at_entry         = Column(Float, nullable=True)
    totp_confirmed         = Column(Boolean, default=False)
    balance_at_open        = Column(Float, nullable=True)
    tier_at_open           = Column(Integer, nullable=True)
    actual_fill_entry      = Column(Float, nullable=True)
    actual_fill_exit       = Column(Float, nullable=True)
    slippage_entry_pct     = Column(Float, nullable=True)
    slippage_exit_pct      = Column(Float, nullable=True)
    entry_commission       = Column(Float, nullable=True)
    exit_commission        = Column(Float, nullable=True)
    total_commission       = Column(Float, nullable=True)
    entry_role             = Column(String, nullable=True)
    exit_role              = Column(String, nullable=True)
    realized_pnl_exchange  = Column(Float, nullable=True)
    funding_fees_paid      = Column(Float, nullable=True)
    net_pnl                = Column(Float, nullable=True)


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

    __table_args__ = (
        UniqueConstraint("coin", "timeframe", "timestamp", name="uq_candle"),
    )


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


class ContentPost(Base):
    __tablename__ = "content_posts"

    id              = Column(Integer, primary_key=True)
    signal_id       = Column(Integer, nullable=False)
    chart_path      = Column(String, nullable=True)
    twitter_draft   = Column(Text, nullable=True)
    long_draft      = Column(Text, nullable=True)
    hashtags        = Column(Text, nullable=True)
    tone_used       = Column(String, nullable=True)
    status          = Column(String, default="pending")
    platform        = Column(String, default="twitter")
    tweet_id        = Column(String, nullable=True)
    posted_at       = Column(DateTime, nullable=True)
    engagement_json = Column(Text, nullable=True)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    edited_text     = Column(Text, nullable=True)


class User(Base):
    __tablename__ = "users"

    id          = Column(Integer, primary_key=True)
    email       = Column(String, unique=True, nullable=False, index=True)
    name        = Column(String, nullable=True)
    avatar      = Column(String, nullable=True)
    provider    = Column(String, default="google")
    provider_id = Column(String, nullable=True)
    tier        = Column(String, default="free")
    is_admin    = Column(Boolean, default=False)
    is_active   = Column(Boolean, default=True)
    onboarded   = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen   = Column(DateTime, nullable=True)
    last_login  = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "provider_id", name="uq_provider_user"),
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id                   = Column(Integer, primary_key=True)
    user_id              = Column(Integer, nullable=False, index=True)
    tier                 = Column(String, default="free")
    status               = Column(String, default="active")
    stripe_customer_id   = Column(String, nullable=True)
    stripe_sub_id        = Column(String, nullable=True)
    stripe_price_id      = Column(String, nullable=True)
    current_period_start = Column(DateTime, nullable=True)
    current_period_end   = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)
    trial_ends_at        = Column(DateTime, nullable=True)
    created_at           = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at           = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes                = Column(Text, nullable=True)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, nullable=False, index=True)
    key_hash   = Column(String, unique=True, nullable=False)
    key_prefix = Column(String, nullable=False)
    name       = Column(String, default="Default")
    tier       = Column(String, default="elite")
    is_active  = Column(Boolean, default=True)
    last_used  = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)


class SignalDelivery(Base):
    __tablename__ = "signal_deliveries"

    id               = Column(Integer, primary_key=True)
    signal_id        = Column(Integer, nullable=False, index=True)
    user_id          = Column(Integer, nullable=False, index=True)
    tier_at_delivery = Column(String, nullable=False)
    delivered_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    was_delayed      = Column(Boolean, default=False)
    delay_minutes    = Column(Integer, default=0)
    levels_shown     = Column(Boolean, default=False)
    factors_shown    = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("signal_id", "user_id", name="uq_signal_delivery"),
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, nullable=False, index=True)
    session_id  = Column(String, unique=True, nullable=False, index=True)
    device      = Column(String, nullable=True)
    browser     = Column(String, nullable=True)
    ip          = Column(String, nullable=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_active = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at  = Column(DateTime, nullable=True)
    is_active   = Column(Boolean, default=True)
    revoked_at  = Column(DateTime, nullable=True)


def init_db():
    Base.metadata.create_all(engine)
    import logging
    logging.getLogger(__name__).info("Database tables created")


init_db()