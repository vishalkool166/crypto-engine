import pytest

from alerts.telegram import client
from alerts.telegram.commands import trading


def test_telegram_renderer_keeps_emoji_and_escapes_untrusted_markup():
    rendered = client.render_message("📈 *ETHUSDT* <script>alert(1)</script>")
    assert "📈" in rendered
    assert "<b>ETHUSDT</b>" in rendered
    assert "&lt;script&gt;" in rendered
    assert "<script>" not in rendered
    assert "Signal Engine · PAPER" in rendered


@pytest.mark.asyncio
async def test_position_command_keeps_core_details_when_sl_and_tp_are_missing(monkeypatch):
    async def positions():
        return [{
            "coin": "ETH",
            "entry_price": 100.0,
            "current_price": 101.0,
            "direction": "LONG",
            "grade": "A",
            "leverage": 2,
            "margin_used": 50.0,
            "profit_abs": 1.0,
            "sl_price": None,
            "tp1_price": None,
            "duration": "2h",
            "health": {"state": "HEALTHY"},
        }]

    messages = []

    async def capture(message):
        messages.append(message)

    monkeypatch.setattr("trade.monitor.get_open_positions_enriched", positions)
    monkeypatch.setattr(trading, "send", capture)

    await trading.cmd_position("ETH")

    assert len(messages) == 1
    assert "ETHUSDT — Position Detail" in messages[0]
    assert "Entry: `$100.000000`" in messages[0]
    assert "Live: `$101.000000`" in messages[0]
    assert "Leverage: `2×`" in messages[0]
    assert "Health: `HEALTHY`" in messages[0]
