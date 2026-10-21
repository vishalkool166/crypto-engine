from config import cfg
from trade.exchange import _base_url, _ws_base_url


def test_paper_mode_uses_current_binance_demo_rest_and_stream_hosts(monkeypatch):
    monkeypatch.setattr(cfg, "TRADING_MODE", "paper")
    assert _base_url() == "https://demo-fapi.binance.com"
    assert _ws_base_url() == "wss://demo-fstream.binance.com"


def test_live_hosts_remain_separate_from_demo_hosts(monkeypatch):
    monkeypatch.setattr(cfg, "TRADING_MODE", "live")
    assert _base_url() == "https://fapi.binance.com"
    assert _ws_base_url() == "wss://fstream.binance.com"
