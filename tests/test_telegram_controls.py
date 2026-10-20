"""Telegram webhook replay and mutating-command authorization checks."""
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from alerts.telegram import router


class FakeRedis:
    def __init__(self):
        self.keys = set()

    def set(self, key, value, *, ex, nx):
        assert ex == 7 * 86400 and nx is True
        if key in self.keys:
            return False
        self.keys.add(key)
        return True


def request(update_id, text, sender_id='42', chat_id='99', chat_type='group', secret='secret'):
    return SimpleNamespace(
        headers={'X-Telegram-Bot-Api-Secret-Token': secret},
        json=AsyncMock(return_value={
            'update_id': update_id,
            'message': {'text': text, 'from': {'id': int(sender_id)},
                        'chat': {'id': int(chat_id), 'type': chat_type}},
        }),
    )


def install_store(monkeypatch, store):
    module = ModuleType('redis_client')
    module.get_redis = lambda: store
    monkeypatch.setitem(__import__('sys').modules, 'redis_client', module)


@pytest.mark.asyncio
async def test_webhook_secret_is_required(monkeypatch):
    monkeypatch.setattr(router.cfg, 'WEBHOOK_SECRET', 'secret')
    with pytest.raises(HTTPException) as exc:
        await router.handle_webhook(request(1, '/status', secret='wrong'))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_mutating_group_command_requires_allowlisted_sender(monkeypatch):
    store = FakeRedis()
    install_store(monkeypatch, store)
    monkeypatch.setattr(router.cfg, 'WEBHOOK_SECRET', 'secret')
    monkeypatch.setattr(router.cfg, 'TELEGRAM_CHAT_ID', '99')
    monkeypatch.setenv('TELEGRAM_ADMIN_USER_IDS', '7, 88')
    handler = AsyncMock()
    monkeypatch.setattr(router, '_handle_command', handler)
    audit_rows = []
    monkeypatch.setattr(router, '_audit_command', lambda text, sender, success: audit_rows.append((text, sender, success)) or True)

    await router.handle_webhook(request(2, '/scan', sender_id='42'))
    handler.assert_not_awaited()
    assert audit_rows[-1][2] is False

    await router.handle_webhook(request(3, '/scan@engine_bot', sender_id='88'))
    handler.assert_awaited_once_with('/scan@engine_bot', '99')
    assert audit_rows[-1][2] is True


@pytest.mark.asyncio
async def test_private_chat_fallback_is_narrow_and_update_replay_is_rejected(monkeypatch):
    store = FakeRedis()
    install_store(monkeypatch, store)
    monkeypatch.setattr(router.cfg, 'WEBHOOK_SECRET', 'secret')
    monkeypatch.setattr(router.cfg, 'TELEGRAM_CHAT_ID', '99')
    monkeypatch.delenv('TELEGRAM_ADMIN_USER_IDS', raising=False)
    handler = AsyncMock()
    monkeypatch.setattr(router, '_handle_command', handler)

    update = request(5, '/discard 10', sender_id='99', chat_id='99', chat_type='private')
    await router.handle_webhook(update)
    handler.assert_awaited_once()
    await router.handle_webhook(request(5, '/discard 10', sender_id='99', chat_id='99', chat_type='private'))
    handler.assert_awaited_once()

    await router.handle_webhook(request(6, '/backfill', sender_id='42', chat_id='99', chat_type='group'))
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_mutation_is_blocked_if_audit_storage_fails(monkeypatch):
    store = FakeRedis()
    install_store(monkeypatch, store)
    monkeypatch.setattr(router.cfg, 'WEBHOOK_SECRET', 'secret')
    monkeypatch.setattr(router.cfg, 'TELEGRAM_CHAT_ID', '99')
    monkeypatch.setenv('TELEGRAM_ADMIN_USER_IDS', '88')
    handler = AsyncMock()
    monkeypatch.setattr(router, '_handle_command', handler)
    monkeypatch.setattr(router, '_audit_command', lambda *args: False)

    await router.handle_webhook(request(7, '/discard 10', sender_id='88'))
    handler.assert_not_awaited()


def test_update_claim_fails_closed_without_shared_redis(monkeypatch):
    module = ModuleType('redis_client')
    module.get_redis = lambda: None
    monkeypatch.setitem(__import__('sys').modules, 'redis_client', module)
    assert router._claim_update(123) is False
    assert router._claim_update(True) is False
    assert router._claim_update('123') is False
