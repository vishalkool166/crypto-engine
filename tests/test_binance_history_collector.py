import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR_PATH = ROOT / 'tools/binance-history-collector/collector.py'
spec = importlib.util.spec_from_file_location('binance_history_collector', COLLECTOR_PATH)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def test_reads_coin_config_as_literal_without_importing_runtime():
    config = collector.read_coin_config(ROOT / 'config.py')
    assert len(config) == 18
    assert config['ETH']['tp'] == 2.0


def test_klines_pagination_and_complete_window(monkeypatch):
    step = collector.INTERVAL_MS['1h']
    start = 1_700_000_000_000 // step * step
    end = start + step * 3
    pages = {
        start: [[start, '1', '2', '0.5', '1.5', '10', start + step - 1, '15', 4, '5', '8', '0'],
                [start + step, '1.5', '2', '1', '1.8', '11', start + step * 2 - 1, '18', 5, '6', '9', '0']],
        start + step * 2: [[start + step * 2, '1.8', '2', '1', '1.9', '12', start + step * 3 - 1, '20', 6, '7', '10', '0']],
    }
    monkeypatch.setattr(collector.time, 'time', lambda: (end + 1000) / 1000)
    monkeypatch.setattr(collector.time, 'sleep', lambda _seconds: None)
    monkeypatch.setattr(collector, 'request_json', lambda _path, params: pages.get(params['startTime'], []))
    rows = collector.fetch_klines('ETHUSDT', '1h', start, end)
    assert [row[0] for row in rows] == [start, start + step, start + step * 2]


def test_refuses_incomplete_candle_window(monkeypatch):
    step = collector.INTERVAL_MS['1h']
    start = 1_700_000_000_000 // step * step
    end = start + step * 3
    rows = [[start, '1', '2', '0.5', '1.5', '10', start + step - 1, '15', 4, '5', '8', '0'],
            [start + step * 2, '1.8', '2', '1', '1.9', '12', start + step * 3 - 1, '20', 6, '7', '10', '0']]
    monkeypatch.setattr(collector.time, 'time', lambda: (end + 1000) / 1000)
    monkeypatch.setattr(collector.time, 'sleep', lambda _seconds: None)
    monkeypatch.setattr(collector, 'request_json', lambda _path, _params: rows)
    with pytest.raises(RuntimeError, match='candle gaps'):
        collector.fetch_klines('ETHUSDT', '1h', start, end)
