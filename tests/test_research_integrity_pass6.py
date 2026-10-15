"""No network access or live trading needed."""
from pathlib import Path
import hashlib
import json
import types
import requests
import pytest

from backtest import research


def test_evaluate_refuses_missing_manifest(tmp_path):
    with pytest.raises(FileNotFoundError, match='missing dataset manifest'):
        research.evaluate('ETH', tmp_path)


def test_evaluate_refuses_missing_funding_checksum(tmp_path):
    (tmp_path / 'ETH_manifest.json').write_text(json.dumps({
        'coin': 'ETH', 'symbol': 'ETHUSDT', 'sha256': {
            'ETH_4h.csv': 'abc', 'ETH_1h.csv': 'def',
        }
    }))
    with pytest.raises(ValueError, match='missing required candle/funding checksums'):
        research.evaluate('ETH', tmp_path)


def test_binance_ip_ban_not_retried(monkeypatch):
    called = []
    class FakeResponse:
        status_code = 418
        headers = {}
        text = 'IP banned'
        def raise_for_status(self):
            raise requests.HTTPError('Binance 418 IP banned')
    class FakeSession:
        def get(self, *args, **kwargs):
            called.append((args,kwargs))
            return FakeResponse()
    monkeypatch.setattr(research.time, 'sleep', lambda _: None)
    with pytest.raises(requests.HTTPError, match='418'):
        research._json(FakeSession(), '/fapi/v1/klines', {})
    assert len(called) == 1


def test_symbol_notional_fail_closed_on_missing_exchange_filter():
    from trade.safety import validate_symbol_notional
    with pytest.raises(ValueError, match='minimum notional unavailable'):
        validate_symbol_notional(100, 1, 0)


def test_research_rejects_unfinished_ohlcv_bar(monkeypatch):
    import time
    now = int(time.time() * 1000)
    step = 4 * 3600_000
    current_open = (now // step) * step
    row = [current_open, '100', '102', '99', '101', '1000']
    monkeypatch.setattr(research, '_json', lambda *args, **kwargs: [row])
    with pytest.raises(ValueError, match='unfinished candle'):
        research.fetch_klines('ETHUSDT', '4h', current_open, current_open + step,
                               session=object())


def test_research_rejects_misaligned_utc_data_window():
    with pytest.raises(ValueError, match='must align'):
        research.fetch_klines('ETHUSDT', '4h', 1, 14400000,
                               session=object())
