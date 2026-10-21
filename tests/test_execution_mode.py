"""Mode changes are tested against fake exchanges; tests never send an order."""
import asyncio
import pytest
from fastapi import HTTPException
from trade import mode
from config import cfg


@pytest.fixture(autouse=True)
def isolated_mode(monkeypatch):
    monkeypatch.setattr(mode, "_transitioning", False)
    monkeypatch.setattr(mode, "_active_operations", 0)
    monkeypatch.setattr(cfg, "TRADING_MODE", "paper")
    monkeypatch.setattr(cfg, "PAPER_TRADING", True)
    monkeypatch.setenv("MODE_SWITCH_RESTART", "true")
    monkeypatch.setenv("ENGINE_ENABLED", "true")
    monkeypatch.setattr(mode, "live_configured", lambda: True)


@pytest.mark.asyncio
async def test_flat_verified_transition_persists_without_hot_swapping(monkeypatch):
    checks, saved = [], {}
    async def flat(value): checks.append(value)
    monkeypatch.setattr(mode, "assert_local_flat", lambda: None)
    monkeypatch.setattr(mode, "assert_account_flat", flat)
    monkeypatch.setattr("runtime_state.set", lambda key, value: saved.update({key: value}))
    result = await mode.request_transition("live", "paper", "operator@example.com")
    assert checks == ["paper", "live"]
    assert saved == {"operator_execution_mode": "live"}
    assert cfg.TRADING_MODE == "paper"  # Active account never changes mid-process.
    assert result["pending_mode"] == "live" and mode.transitioning()
    with pytest.raises(RuntimeError): mode.assert_writes_allowed("/fapi/v1/order")


@pytest.mark.asyncio
async def test_exposure_or_account_probe_failure_never_persists(monkeypatch):
    saved = []
    monkeypatch.setattr(mode, "assert_local_flat", lambda: None)
    async def blocked(_): raise HTTPException(409, "Open exchange position")
    monkeypatch.setattr(mode, "assert_account_flat", blocked)
    monkeypatch.setattr("runtime_state.set", lambda *args: saved.append(args))
    with pytest.raises(HTTPException): await mode.request_transition("live", "paper", "operator")
    assert not saved and not mode.transitioning()


@pytest.mark.asyncio
async def test_active_execution_and_stale_mode_block_switch(monkeypatch):
    monkeypatch.setattr(mode, "_active_operations", 1)
    with pytest.raises(HTTPException, match="409"): await mode.request_transition("live", "paper", "operator")
    assert not mode.transitioning()
    with pytest.raises(HTTPException): await mode.request_transition("paper", "live", "operator")


@pytest.mark.asyncio
async def test_guard_holds_across_await_and_releases_on_error():
    @mode.guard_operation
    async def work():
        assert mode._active_operations == 1
        await asyncio.sleep(0)
        raise ValueError("test")
    with pytest.raises(ValueError): await work()
    assert mode._active_operations == 0


def test_restart_restores_authoritative_mode_without_fallback(monkeypatch):
    monkeypatch.setenv("SIGNAL_ENGINE_ALLOW_LIVE_TRADING", "I_UNDERSTAND_REAL_ORDERS")
    monkeypatch.setattr("runtime_state.get", lambda key, default=None: "live")
    assert mode.restore_mode() == "live"
    assert cfg.TRADING_MODE == "live" and cfg.PAPER_TRADING is False
    monkeypatch.setattr(mode, "live_configured", lambda: False)
    with pytest.raises(RuntimeError): mode.restore_mode()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [[{"positionAmt":"1"}], "malformed"])
async def test_exchange_preflight_rejects_exposure_and_malformed_responses(monkeypatch, payload):
    import httpx
    class Response:
        def raise_for_status(self): pass
        def __init__(self, value): self.value = value
        def json(self): return self.value
    class Client:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url):
            if "positionRisk" in url: return Response(payload)
            if "dual" in url: return Response({"dualSidePosition":False})
            return Response([])
    monkeypatch.setattr(httpx, "AsyncClient", Client)
    monkeypatch.setattr(mode, "credentials", lambda _: ("fake", "fake"))
    with pytest.raises(HTTPException): await mode.assert_account_flat("live")


@pytest.fixture
def operator_client():
    import main
    import operator_auth
    from portal_settings import settings
    from fastapi.testclient import TestClient
    main._buckets.clear()
    with TestClient(main.app) as client:
        token = operator_auth.create_operator_session({"email": settings.admin_emails[0], "sub":"google-123", "email_verified":True})
        client.cookies.set(settings.cookie_name, token)
        csrf = client.get("/auth/session").json()["csrf"]
        yield client, {"Origin":settings.admin_origin,"X-CSRF-Token":csrf}


class StepupStore:
    def __init__(self): self.values = {}
    def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]
    def expire(self, *args): return True
    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values: return False
        self.values[key] = value
        return True


def test_mode_endpoint_checks_csrf_and_authenticator(operator_client, monkeypatch):
    client, headers = operator_client
    body = {"target":"live","expected_mode":"paper","confirmation":"ENABLE LIVE TRADING","totp_code":"123456"}
    monkeypatch.setattr("redis_client.get_redis", lambda: StepupStore())
    monkeypatch.setattr("auth.verify_totp", lambda _:False)
    assert client.post("/api/v1/admin/execution/mode",json=body).status_code == 403
    assert client.post("/api/v1/admin/execution/mode",json=body,headers=headers).status_code == 401
    assert client.get("/api/v1/admin/execution/mode").status_code == 200
    client.cookies.clear()
    assert client.get("/api/v1/admin/execution/mode").status_code == 401


def test_accepted_mode_change_schedules_restart_only_after_preflight(operator_client, monkeypatch):
    client, headers = operator_client
    called=[]
    monkeypatch.setattr("redis_client.get_redis", lambda: StepupStore())
    monkeypatch.setattr("auth.verify_totp", lambda _:True)
    async def transition(*args):
        called.append("preflight")
        return {"success":True,"pending_mode":"live"}
    async def restart(): called.append("restart")
    monkeypatch.setattr(mode,"request_transition",transition)
    monkeypatch.setattr(mode,"restart_process",restart)
    body = {"target":"live","expected_mode":"paper","confirmation":"ENABLE LIVE TRADING","totp_code":"123456"}
    response=client.post("/api/v1/admin/execution/mode",json=body,headers=headers)
    assert response.status_code == 202
    assert called == ["preflight","restart"]


def test_totp_code_is_single_use_and_fails_without_redis(monkeypatch):
    import auth, pyotp
    secret = pyotp.random_base32()
    store = StepupStore()
    monkeypatch.setattr(cfg, "TOTP_SECRET", secret)
    monkeypatch.setattr("redis_client.get_redis", lambda:store)
    code = pyotp.TOTP(secret).now()
    assert auth.verify_totp(code) is True
    assert auth.verify_totp(code) is False
    monkeypatch.setattr("redis_client.get_redis", lambda:None)
    assert auth.verify_totp(code) is False
