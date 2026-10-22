"""Persisted strategy permissions in the existing SQLite database.

Scanning and execution are deliberately separate. All four participate in
scanning by default; paper execution is ready without configuration. The
existing account-level paper/live safeguard is never bypassed here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, String
from database import Base, get_session
from strategies.registry import STRATEGIES


class StrategyControl(Base):
    __tablename__ = 'strategy_controls'
    strategy = Column(String(50), primary_key=True)
    scan_enabled = Column(Boolean, nullable=False, default=True)
    execution_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


def ensure_controls() -> None:
    """Idempotent migration compatible with existing installations."""
    StrategyControl.__table__.create(bind=__import__('database').engine, checkfirst=True)
    with get_session() as db:
        for strategy in STRATEGIES:
            if db.get(StrategyControl, strategy) is None:
                db.add(StrategyControl(strategy=strategy, scan_enabled=True,
                                       execution_enabled=True))


def get_controls() -> dict[str, dict]:
    with get_session() as db:
        rows = {r.strategy:r for r in db.query(StrategyControl).all()}
        return {k:{'scan_enabled':bool(rows[k].scan_enabled),
                   'execution_enabled':bool(rows[k].execution_enabled),
                   'updated_at':rows[k].updated_at.isoformat() if rows[k].updated_at else None}
                for k in STRATEGIES if k in rows}


def update_control(strategy: str, *, scan_enabled: bool, execution_enabled: bool) -> dict:
    if strategy not in STRATEGIES:
        raise ValueError('Unknown strategy')
    if not scan_enabled and execution_enabled:
        raise ValueError('Execution cannot be enabled for a disabled scanner')
    with get_session() as db:
        row = db.get(StrategyControl, strategy)
        if row is None:
            raise RuntimeError('Strategy control not initialized')
        row.scan_enabled = scan_enabled
        row.execution_enabled = execution_enabled
        row.updated_at = datetime.now(timezone.utc)
    return get_controls()[strategy]
