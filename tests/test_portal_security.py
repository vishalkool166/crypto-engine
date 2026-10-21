import hashlib
import json
from dataclasses import replace
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import text
import main
import operator_auth as auth
from portal_settings import settings
from database import engine, SessionLocal, Signal, Trade


@pytest.fixture(autouse=True)
def isolated():
    auth.init_operator_schema()
    with engine.begin() as db:
        db.execute(text("DELETE FROM operator_sessions"))
        db.execute(text("DELETE FROM operator_identities"))
        db.execute(text("DELETE FROM signals"))
        db.execute(text("DELETE FROM trades"))
    main._buckets.clear()
    from api.portal import _snapshot

    _snapshot["at"] = 0
    yield


@pytest.fixture
def client():
    with TestClient(main.app) as value:
        yield value


def identity(**extra):
    return {
        "email": settings.admin_emails[0],
        "sub": "google-123",
        "email_verified": True,
        **extra,
    }


def login(client):
    token = auth.create_operator_session(identity())
    client.cookies.set(settings.cookie_name, token)
    return client.get("/auth/session").json()["csrf"]


@pytest.mark.parametrize(
    "info",
    [
        identity(email="different@example.com"),
        identity(email_verified=False),
        identity(email_verified="true"),
        identity(sub=""),
        {"email": settings.admin_emails[0]},
    ],
)
def test_google_identity_requires_verified_allowlisted_subject(info):
    with pytest.raises(HTTPException):
        auth.create_operator_session(info)


def test_google_subject_cannot_be_rebound():
    auth.create_operator_session(identity())
    with pytest.raises(HTTPException):
        auth.create_operator_session(identity(sub="other-subject"))


def test_session_is_hashed_revocable_and_expiring(client):
    csrf = login(client)
    raw = client.cookies.get(settings.cookie_name)
    with engine.connect() as db:
        stored = db.execute(text("SELECT token_hash FROM operator_sessions")).scalar()
    assert stored != raw and stored == hashlib.sha256(raw.encode()).hexdigest()
    assert (
        client.post(
            "/auth/logout",
            headers={"Origin": settings.admin_origin, "X-CSRF-Token": csrf},
        ).status_code
        == 200
    )
    assert client.get("/auth/session").status_code == 401
    login(client)
    with engine.begin() as db:
        db.execute(text("UPDATE operator_sessions SET expires_at=0"))
    assert client.get("/auth/session").status_code == 401


def test_no_parallel_password_or_master_key_login(client):
    assert client.post("/auth/login", json={"password": "anything"}).status_code == 404
    assert (
        client.get(
            "/api/v1/admin/settings", headers={"X-API-Key": "old-key"}
        ).status_code
        == 401
    )


def test_admin_api_requires_session_and_csrf(client):
    assert client.get("/api/v1/admin/settings").status_code == 401
    csrf = login(client)
    assert client.get("/api/v1/admin/settings").status_code == 200
    assert client.post("/api/v1/admin/scan").status_code == 403
    assert (
        client.post(
            "/api/v1/admin/scan",
            headers={"Origin": "https://attacker.invalid", "X-CSRF-Token": csrf},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/admin/scan",
            headers={"Origin": settings.admin_origin, "X-CSRF-Token": csrf},
        ).status_code
        == 409
    )


def test_data_catalog_is_private_and_redacts_operator_session_secrets(client):
    assert client.get("/api/v1/admin/data/catalog").status_code == 401
    login(client)

    catalog = client.get("/api/v1/admin/data/catalog")
    assert catalog.status_code == 200
    names = {table["name"] for table in catalog.json()["tables"]}
    assert {"signals", "trades", "trade_journey", "portfolio_snapshots"} <= names
    assert "operator_sessions" in names

    sessions = client.get("/api/v1/admin/data/operator_sessions?limit=5")
    assert sessions.status_code == 200
    result = sessions.json()
    assert result["total"] >= 1
    assert all(row["token_hash"] == "[REDACTED]" for row in result["rows"])
    assert all(row["csrf"] == "[REDACTED]" for row in result["rows"])


def test_performance_context_uses_persisted_trades_and_factor_scores(client):
    assert client.get("/api/v1/admin/performance/context").status_code == 401
    login(client)
    with SessionLocal() as db:
        db.add_all([
            Trade(coin="ETH", direction="LONG", grade="A", outcome="win", system_version="2.0.0", regime_at_entry="trend", net_pnl=5.0),
            Trade(coin="SOL", direction="SHORT", grade="B", outcome="loss", system_version="2.0.0", regime_at_entry="range", net_pnl=-2.0),
            Signal(coin="ETH", market="crypto", direction="LONG", grade="A", score=70, outcome="win", factor_scores=json.dumps({"score_breakdown": {"momentum": 8}})),
            Signal(coin="SOL", market="crypto", direction="SHORT", grade="B", score=55, outcome="loss", factor_scores=json.dumps({"score_breakdown": {"momentum": 4}})),
        ])
        db.commit()

    response = client.get("/api/v1/admin/performance/context")
    assert response.status_code == 200
    data = response.json()
    assert data["by_version"][0]["system_version"] == "2.0.0"
    assert data["by_version"][0]["total"] == 2
    assert {row["regime_at_entry"] for row in data["by_regime"]} == {"trend", "range"}
    factor = next(row for row in data["factors"] if row["factor"] == "momentum")
    assert factor["observations"] == 2
    assert factor["mean_score_wins"] == 8
    assert factor["mean_score_losses"] == 4


def test_public_hostname_cannot_address_admin(client):
    login(client)
    assert (
        client.get(
            "/api/v1/admin/settings",
            headers={"X-Forwarded-App-Host": settings.public_host},
        ).status_code
        == 404
    )


def test_origin_proxy_secret_is_required_in_production(client, monkeypatch):
    prod = replace(settings, production=True, origin_secret="x" * 48)
    monkeypatch.setattr(main, "settings", prod)
    assert client.get("/api/v1/public/status").status_code == 403
    assert (
        client.get(
            "/api/v1/public/status",
            headers={
                "X-Origin-Verify": "x" * 48,
                "X-Forwarded-App-Host": settings.public_host,
            },
        ).status_code
        == 200
    )


def test_public_projection_excludes_account_fields(client):
    with SessionLocal() as db:
        row = Signal(
            coin="ETH",
            market="crypto",
            direction="LONG",
            grade="A",
            score=70,
            entry=100,
            sl=95,
            tp1=110,
            risk_amt=999,
            position=1234,
            notes="private-account",
            factor_scores=json.dumps(
                {
                    "steps": [
                        {"node": "grade", "score": 70},
                        {"node": "sizing", "risk_amt": 999},
                    ]
                }
            ),
        )
        db.add(row)
        db.commit()
        sid = row.id
    data = client.get("/api/v1/public/signals").json()
    serialized = json.dumps(data)
    assert (
        "risk_amt" not in serialized
        and "position" not in serialized
        and "private-account" not in serialized
    )
    detail = client.get("/api/v1/public/signals/" + str(sid)).json()
    assert detail["trace"] == [{"node": "grade", "score": 70}]
    assert client.get("/api/v1/public/signals?limit=100000").status_code == 422


def test_retired_routes_are_absent(client):
    csrf = login(client)
    headers = {"Origin": settings.admin_origin, "X-CSRF-Token": csrf}
    for path in (
        "/api/v1/admin/trades/mode",
        "/api/v1/admin/system/docker-purge",
        "/api/v1/admin/users",
    ):
        assert client.post(path, headers=headers).status_code == 404
    assert client.get("/api/pricing").status_code == 404
    health = client.get("/api/v1/admin/health").json()
    assert "checks" in health and "redis" in health["checks"]


def test_http_budget_and_body_limit(client):
    for _ in range(20):
        client.get("/auth/google")
    assert client.get("/auth/google").status_code == 429
    main._buckets.clear()
    assert client.post("/webhook/telegram", content="x" * 65537).status_code == 413


def test_private_ws_rejects_missing_session_and_cross_site(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/ws/admin", headers={"Origin": settings.admin_origin}
        ):
            pass
    login(client)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/ws/admin", headers={"Origin": "https://attacker.invalid"}
        ):
            pass


def test_public_ws_uses_public_projection(client, monkeypatch):
    monkeypatch.setattr(
        main, "public_snapshot", lambda: {"mode": "paper", "status": "awaiting_data"}
    )
    with client.websocket_connect(
        "/ws/public", headers={"Origin": settings.public_origin}
    ) as ws:
        assert ws.receive_json() == {"mode": "paper", "status": "awaiting_data"}


def test_private_ws_accepts_valid_operator(client, monkeypatch):
    from api import portal

    monkeypatch.setattr(
        portal,
        "private_health",
        lambda _: {"mode": "paper", "checks": {"redis": "unknown"}},
    )
    login(client)
    with client.websocket_connect(
        "/ws/admin", headers={"Origin": settings.admin_origin}
    ) as ws:
        assert ws.receive_json()["checks"]["redis"] == "unknown"


def test_unknown_redis_is_not_falsely_connected(client, monkeypatch):
    import redis_client

    monkeypatch.setattr(redis_client, "get_redis", lambda: None)
    login(client)
    health = client.get("/api/v1/admin/health").json()
    assert health["checks"]["redis"] == "disconnected"
    assert health["checks"]["database"] == "connected"


def test_live_configuration_is_refused(monkeypatch):
    monkeypatch.setenv("TRADING_MODE", "live")
    with pytest.raises(RuntimeError, match="paper"):
        settings.validate()


def test_telegram_html_is_escaped():
    from alerts.telegram.client import render_message

    message = render_message("*Report* and " + chr(96) + "ETH" + chr(96) + " <script>&")
    assert "<b>Report</b>" in message and "<code>ETH</code>" in message
    assert "&lt;script&gt;&amp;" in message and "PAPER" in message


def test_indian_status_is_read_only_and_never_downloads_master(client, monkeypatch):
    import engines.indian.instruments as instruments
    def forbidden():
        raise AssertionError('Dashboard read must not download instrument catalogue')
    monkeypatch.setattr(instruments, '_download_master', forbidden)
    monkeypatch.setattr(instruments, '_instruments', {})
    login(client)
    response=client.get('/api/v1/admin/indian/status')
    assert response.status_code==200
    assert response.json()['instruments']=={}


def test_empty_universe_initialization_preserves_existing_disabled_configuration():
    from database import CoinConfig, initialize_universe
    from config import COIN_CONFIG, REMOVED_COINS
    with SessionLocal() as db:
        original=[{k:getattr(r,k) for k in ('coin','enabled','tier','source','market')} for r in db.query(CoinConfig).all()]
        db.query(CoinConfig).delete();db.commit()
    try:
        initialize_universe()
        with SessionLocal() as db:
            assert {r.coin for r in db.query(CoinConfig)}==set(COIN_CONFIG)-set(REMOVED_COINS)
            row=db.query(CoinConfig).first();coin=row.coin;row.enabled=False;db.commit()
        initialize_universe()
        with SessionLocal() as db:
            assert db.query(CoinConfig).filter_by(coin=coin).one().enabled is False
    finally:
        with SessionLocal() as db:
            db.query(CoinConfig).delete()
            db.add_all([CoinConfig(**r) for r in original]);db.commit()
