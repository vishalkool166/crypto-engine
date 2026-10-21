"""Crash-resilient, single-submission intent journal for Binance REST orders.

A reservation is committed *before* network I/O. Reusing an intent never
resubmits an order: the caller must reconcile by the saved client order ID.
The database must reside on durable storage and be backed up with the trade DB.
"""
from __future__ import annotations

import os
import hashlib
import json
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB = Path('database/signals.db')
_SETUP_LOCK = threading.Lock()
_INITIALIZED_PATHS = set()
_VALID_INTENT = re.compile(r'^[A-Za-z0-9_.:-]{1,120}$')


class OrderIntentConflict(RuntimeError):
    pass


def _path() -> Path:
    # Production journal MUST share the durable trade DB, not Redis or a
    # separate non-backed-up file. Override is only for isolated pytest runs.
    override = os.environ.get('SIGNAL_ENGINE_DB_PATH')
    if override and Path(override).resolve() != DEFAULT_DB.resolve() and not os.environ.get('PYTEST_CURRENT_TEST'):
        raise RuntimeError('SIGNAL_ENGINE_DB_PATH override is restricted to tests')
    return Path(override) if override else DEFAULT_DB


@contextmanager
def _connection():
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    try:
        db.execute('PRAGMA busy_timeout=30000')
        # Switching SQLite to WAL on EVERY connection races with concurrent
        # reservations. Initialize the schema once per local database path.
        with _SETUP_LOCK:
            resolved = path.resolve()
            if resolved not in _INITIALIZED_PATHS:
                db.execute('PRAGMA journal_mode=WAL')
                db.execute('''CREATE TABLE IF NOT EXISTS exchange_order_intents (
                    intent_key TEXT PRIMARY KEY,
                    client_order_id TEXT NOT NULL UNIQUE,
                    mode TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('reserved', 'acknowledged', 'uncertain', 'finished')),
                    exchange_order_id TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )''')
                _INITIALIZED_PATHS.add(resolved)
        db.execute('PRAGMA synchronous=FULL')
        yield db
    finally:
        db.close()


def reserve(intent_key: str, mode: str, symbol: str, side: str, order_type: str,
            request_payload: dict | None = None) -> tuple[str, bool]:
    """Return (client_order_id, is_new). Existing keys cannot change meaning."""
    if not _VALID_INTENT.fullmatch(intent_key):
        raise ValueError('Invalid order intent key')
    if mode not in ('paper', 'live'):
        raise ValueError('Invalid exchange mode')
    fingerprint = hashlib.sha256(json.dumps(
        request_payload or {}, sort_keys=True, allow_nan=False,
        separators=(',', ':'), default=str,
    ).encode()).hexdigest()
    client_id = 'se_' + uuid.uuid4().hex
    with _connection() as db:
        db.execute('BEGIN IMMEDIATE')
        try:
            row = db.execute('''SELECT client_order_id, mode, symbol, side, order_type, request_sha256
                                FROM exchange_order_intents WHERE intent_key=?''', (intent_key,)).fetchone()
            if row:
                if row[1:] != (mode, symbol, side, order_type, fingerprint):
                    raise OrderIntentConflict(f'Order intent {intent_key} cannot be reused with different parameters')
                db.execute('COMMIT')
                return row[0], False
            db.execute('''INSERT INTO exchange_order_intents
                (intent_key, client_order_id, mode, symbol, side, order_type, request_sha256, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'reserved')''',
                (intent_key, client_id, mode, symbol, side, order_type, fingerprint))
            db.execute('COMMIT')
            return client_id, True
        except BaseException:
            db.execute('ROLLBACK')
            raise


def mark(intent_key: str, status: str, exchange_order_id: str | None = None) -> None:
    if status not in ('acknowledged', 'uncertain', 'finished'):
        raise ValueError('Invalid intent status')
    with _connection() as db:
        cursor = db.execute('''UPDATE exchange_order_intents SET status=?,
            exchange_order_id=COALESCE(?, exchange_order_id), updated_at=CURRENT_TIMESTAMP
            WHERE intent_key=?''', (status, exchange_order_id, intent_key))
        if cursor.rowcount != 1:
            raise RuntimeError(f'Order intent missing: {intent_key}')


def unresolved(symbol: str | None = None) -> list[dict]:
    """Any unfinalized order intent blocks new exposure until reconciled."""
    with _connection() as db:
        query = '''SELECT intent_key, client_order_id, mode, symbol, status
                   FROM exchange_order_intents WHERE status != 'finished' '''
        params = ()
        if symbol:
            query += ' AND symbol=?'
            params = (symbol,)
        query += ' ORDER BY created_at ASC'
        return [dict(zip(('intent_key','client_order_id','mode','symbol','status'), row))
                for row in db.execute(query, params)]
