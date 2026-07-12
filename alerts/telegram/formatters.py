import logging
from datetime import datetime, timezone, timedelta, date
from database import SessionLocal, Signal as SignalModel
from data.cache import cache
from config import cfg

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> str:
    return datetime.now(IST).strftime("%I:%M %p IST")


def now_ist_full() -> str:
    return datetime.now(IST).strftime("%d %b %Y · %I:%M %p IST")


def get_stats() -> dict:
    from alerts.scanner import get_db_stats
    return get_db_stats()


def get_cached(coin: str) -> dict | None:
    return cache.get_raw(f"signal_{coin}")


def all_cached_signals() -> list:
    return [c for coin in cfg.COINS if (c := cache.get_raw(f"signal_{coin}"))]


def grade_block(label: str, data: dict) -> str:
    return (
        f"*Grade {label}*\n"
        f"Trades:   `{data.get('total', 0)}`\n"
        f"Wins:     `{data.get('wins', 0)}`\n"
        f"Losses:   `{data.get('losses', 0)}`\n"
        f"Win Rate: `{data.get('win_rate', 0)}%`\n"
        f"PnL:      `${data.get('total_pnl', 0)}`\n"
    )


def get_trading_session() -> dict:
    hour = datetime.now(timezone.utc).hour
    if 8  <= hour < 13: return {"name": "London"}
    if 13 <= hour < 17: return {"name": "London/NY Overlap"}
    if 17 <= hour < 21: return {"name": "New York"}
    if 0  <= hour < 8:  return {"name": "Asia"}
    return {"name": "Off Hours"}


def get_in_trade_count() -> int:
    try:
        from database import Trade as TradeModel
        with SessionLocal() as db:
            return db.query(TradeModel).filter(
                TradeModel.is_active == True
            ).count()
    except Exception:
        return 0


def get_today_pnl() -> tuple[float, int]:
    try:
        from database import Trade as TradeModel
        today_start = datetime(
            date.today().year,
            date.today().month,
            date.today().day,
            tzinfo=timezone.utc,
        )
        with SessionLocal() as db:
            sigs = db.query(TradeModel).filter(
                TradeModel.closed_at >= today_start,
                TradeModel.outcome.in_(["win", "loss"]),
            ).all()
            return (
                sum(float(s.pnl or 0) for s in sigs),
                len(sigs),
            )
    except Exception:
        return 0.0, 0