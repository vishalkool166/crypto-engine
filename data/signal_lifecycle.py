"""Expire old actionable signals; never destroy historical evidence or open trades."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import or_
from database import Signal, Trade, get_session

DEFAULT_MAX_AGE_HOURS = 12


def expire_actionable_signals(*, max_age_hours: int = DEFAULT_MAX_AGE_HOURS) -> int:
    if not 1 <= max_age_hours <= 168:
        raise ValueError('Signal expiry must be 1–168 hours')
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=max_age_hours)
    with get_session() as db:
        # Open trades must remain reconciled and visible; their source signals
        # are not expired even if the signal timestamp is old.
        opened = db.query(Trade.signal_id).filter(or_(Trade.state.is_(None), Trade.state != 'closed'), Trade.signal_id.isnot(None))
        rows = (db.query(Signal).filter(Signal.outcome == 'pending',
               Signal.timestamp < cutoff, ~Signal.id.in_(opened)).all())
        for row in rows:
            row.outcome = 'expired'
        return len(rows)
