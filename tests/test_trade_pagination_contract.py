from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException
pytest.importorskip("bcrypt", reason="API auth dependencies unavailable in offline runner")
from api.trading import trades_history


@pytest.mark.asyncio
async def test_history_invalid_page_is_rejected_before_database():
    with patch('api.trading._auth'):
        with pytest.raises(HTTPException) as info:
            await trades_history(MagicMock(), limit=101)
    assert info.value.status_code == 422


@pytest.mark.asyncio
async def test_history_server_total_is_not_page_length():
    with patch('api.trading._auth'), patch('trade.monitor.get_trade_history',return_value=[{'trade_id': 17}]) as page, patch('trade.monitor.count_trade_history',return_value=371) as count:
        response = await trades_history(MagicMock(), limit=25, offset=50, grade='A')
    import json
    data=json.loads(response.body)
    assert data['trades_count']==371 and len(data['trades'])==1
    assert data['offset']==50 and data['limit']==25
    page.assert_called_once_with(limit=25,offset=50,outcome=None,grade='A',coin=None,closed_only=True)
    count.assert_called_once()


@pytest.mark.asyncio
async def test_history_coin_input_bounded():
    with patch('api.trading._auth'):
        with pytest.raises(HTTPException) as info:
            await trades_history(MagicMock(),coin='\\%')
    assert info.value.status_code == 422
