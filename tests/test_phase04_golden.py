"""Canonical, deterministic signal decisions; no exchange or order side effects."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from engines.scoring.scorer import _grade, score


@pytest.mark.parametrize('inputs, expected', [
    ((30, 45, 2, 'LONG', 'trending'), (100.0, 'A+', 40.0, 30.0, 30.0)),
    ((25, 50, 1.5, 'LONG', 'trending'), (70.0, 'A', 30.0, 20.0, 20.0)),
    ((20, 55, 1, 'SHORT', 'ranging'), (60.0, 'B', 20.0, 30.0, 10.0)),
    ((19.9, 39, .99, 'LONG', 'ranging'), (0.0, 'F', 0.0, 0.0, 0.0)),
])
def test_canonical_signal_score_outputs(inputs, expected):
    result = score(*inputs)
    observed = (result.total, result.grade, result.adx_pts, result.rsi_pts, result.vol_pts)
    assert observed == expected


@pytest.mark.parametrize('total, expected', [
    (80.0, 'A+'), (79.9, 'A'), (65.0, 'A'),
    (64.9, 'B'), (50.0, 'B'), (49.9, 'F'),
])
def test_canonical_grade_thresholds(total, expected):
    assert _grade(total) == expected


@pytest.mark.asyncio
async def test_market_fetcher_excludes_latest_unfinished_exchange_candle(monkeypatch):
    from data import fetcher

    base = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    raw = [
        [base, 100, 102, 99, 101, 10],
        [base + 14_400_000, 101, 103, 100, 102, 11],
        # Simulated in-progress 4h bar must not enter indicator calculations.
        [base + 28_800_000, 102, 120, 101, 119, 12],
    ]

    class FakeExchange:
        async def fetch_ohlcv(self, *args, **kwargs):
            return raw

    saved = []
    monkeypatch.setattr(fetcher, 'exchange', FakeExchange())
    monkeypatch.setattr(fetcher, 'get_last_timestamp', lambda coin, tf: None)
    monkeypatch.setattr(fetcher, 'save_candles', lambda coin, tf, frame: saved.append(frame.copy()))
    monkeypatch.setattr(fetcher, 'load_candles', lambda coin, tf, limit: saved[-1])

    result = await fetcher.fetch_and_store('ETH', '4h', limit=3)
    assert len(result) == 2
    assert len(saved[0]) == 2
    assert result['close'].tolist() == [101, 102]
    assert result['high'].max() == 103
