import pytest
from alerts.telegram import router, service
from config import cfg


class Store:
    def __init__(self): self.values = {}
    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values: return False
        self.values[key] = value
        return True
    def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]
    def expire(self, *args, **kwargs): return True


@pytest.mark.asyncio
async def test_real_start_help_ping_dispatch_with_bot_suffix_and_dedup(monkeypatch):
    store, messages = Store(), []
    monkeypatch.setattr(cfg, "TELEGRAM_CHAT_ID", "-100123")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "42")
    monkeypatch.setattr("redis_client.get_redis", lambda: store)
    async def capture(message): messages.append(message)
    monkeypatch.setattr("alerts.telegram.client.send", capture)
    monkeypatch.setattr("alerts.telegram.commands.help.send", capture)
    for i, command in enumerate(["/start", "/help@MyBot", "/ping"]):
        payload = {"update_id": 100+i, "message": {"chat":{"id":-100123}, "from":{"id":42}, "text":command}}
        await router.handle_update(payload)
        await router.handle_update(payload)
    assert len(messages) == 3
    assert "Commands" in messages[0] and "Commands" in messages[1]
    assert "reached Signal Engine" in messages[2]
    assert service.status()["last_result"] == "completed"


@pytest.mark.asyncio
async def test_rejected_sender_is_visible_in_diagnostics(monkeypatch):
    monkeypatch.setattr(cfg, "TELEGRAM_CHAT_ID", "-100123")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "42")
    await router.handle_update({"update_id":9,"message":{"chat":{"id":-100123},"from":{"id":99},"text":"/help"}})
    assert service.status()["last_result"] == "sender_not_allowed"


@pytest.mark.asyncio
async def test_polling_replaces_stale_webhook_and_dispatches(monkeypatch):
    import httpx
    class Redis(Store):
        def get(self, key): return self.values.get(key)
        def eval(self, *args): return 1
    store, seen, called = Redis(), [], []
    monkeypatch.setattr("redis_client.get_redis", lambda: store)
    monkeypatch.setattr(cfg, "TELEGRAM_TOKEN", "fake-test-only")
    class Response:
        def __init__(self, result): self.result = result
        def json(self): return self.result
    class Client:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, json=None):
            called.append(url.rsplit("/",1)[-1])
            if url.endswith("getUpdates"):
                if len(seen): raise __import__('asyncio').CancelledError()
                return Response({"ok":True,"result":[{"update_id":123,"message":{}}]})
            return Response({"ok":True})
    async def handle(update): seen.append(update)
    async def register(): return True
    monkeypatch.setattr(httpx, "AsyncClient", Client)
    monkeypatch.setattr(router, "handle_update", handle)
    monkeypatch.setattr("alerts.telegram.client.register_commands", register)
    with pytest.raises(__import__('asyncio').CancelledError): await service._poll()
    assert called[0] == "deleteWebhook"
    assert seen[0]["update_id"] == 123
    assert store.get("telegram:poll-offset") == 124
