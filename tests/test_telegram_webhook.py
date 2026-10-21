import json

from fastapi.testclient import TestClient
import main
import config
import alerts.telegram.router as telegram_router


class FakeRedis:
    def __init__(self):
        self.values = {}

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    def expire(self, key, seconds, nx=False):
        return True


def _post_update(client, text, *, chat_id=-100123, sender_id=42, update_id=9001):
    body = {
        "update_id": update_id,
        "message": {
            "text": text,
            "chat": {"id": chat_id},
            "from": {"id": sender_id},
        },
    }
    return client.post(
        "/webhook/telegram",
        content=json.dumps(body),
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-webhook-secret"},
    )


def _configure(monkeypatch):
    monkeypatch.setattr(config.cfg, "WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setattr(config.cfg, "TELEGRAM_CHAT_ID", "-100123")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "42")
    monkeypatch.setattr("redis_client.get_redis", lambda: FakeRedis())


def test_group_chat_allowed_sender_reaches_journey_command(monkeypatch):
    _configure(monkeypatch)
    seen = []

    async def capture(text, chat_id=""):
        seen.append((text, chat_id))

    monkeypatch.setattr(telegram_router, "_handle_command", capture)
    with TestClient(main.app) as client:
        response = _post_update(client, "/journey 42")

    assert response.status_code == 200
    assert seen == [("/journey 42", "-100123")]


def test_group_chat_unlisted_sender_is_ignored(monkeypatch):
    _configure(monkeypatch)
    seen = []

    async def capture(text, chat_id=""):
        seen.append((text, chat_id))

    monkeypatch.setattr(telegram_router, "_handle_command", capture)
    with TestClient(main.app) as client:
        response = _post_update(client, "/health", sender_id=99, update_id=9002)

    assert response.status_code == 200
    assert seen == []
