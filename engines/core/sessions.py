"""Deterministic UTC session policy shared by live sizing and research.

Session boundaries refer to UTC clock hours, not local market daylight time.
These are deliberately the historical rules of Signal Engine; changing the
schedule requires an explicit research decision and independent validation.
"""
from __future__ import annotations
from datetime import datetime, timezone


def session_at(instant: datetime) -> str:
    """Return one canonical session name for a timezone-aware timestamp."""
    if instant.tzinfo is None:
        raise ValueError('Session evaluation requires a timezone-aware timestamp')
    hour = instant.astimezone(timezone.utc).hour
    if 0 <= hour < 8:
        return 'Asia'
    if 8 <= hour < 13:
        return 'London'
    if 13 <= hour < 17:
        return 'London/NY Overlap'
    if 17 <= hour < 21:
        return 'New York'
    return 'Off Hours'


def session_matches(preferred: str, instant: datetime) -> bool:
    """Whether a coin session is eligible (excluding Off Hours for all coins)."""
    actual = session_at(instant)
    if actual == 'Off Hours':
        return False
    return {
        'all': True,
        'asia': actual == 'Asia',
        'london': actual in ('London', 'London/NY Overlap'),
        'ny': actual in ('New York', 'London/NY Overlap'),
    }.get((preferred or 'all').lower(), False)
