"""API key scope, expiry and revocation checks using disposable SQLite."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
from saas import middleware
from saas import users


@pytest.fixture
def api_key_store(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    database.Base.metadata.create_all(engine, tables=[database.User.__table__, database.ApiKey.__table__])
    maker = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def session():
        db = maker()
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    monkeypatch.setattr(users, "get_session", session)
    monkeypatch.setattr(database, "get_session", session)
    with session() as db:
        db.add(database.User(email="admin@example.test", provider="google", provider_id="google-admin",
                             tier="admin", is_admin=True, is_active=True))
    yield session
    engine.dispose()


def test_created_api_key_is_hashed_and_expires(api_key_store):
    result = users.create_api_key_for_user(1, "build integration")
    assert result["success"] is True
    assert result["key"].startswith("se_")
    expires_at = datetime.fromisoformat(result["expires_at"])
    assert timedelta(days=89) < expires_at - datetime.now(timezone.utc) <= timedelta(days=90, seconds=2)
    with api_key_store() as db:
        row = db.query(database.ApiKey).one()
        assert row.key_hash != result["key"]
        assert row.expires_at is not None


def test_personal_api_key_is_read_only_and_never_admin(api_key_store):
    result = users.create_api_key_for_user(1, "integration")
    request = SimpleNamespace(method="GET", headers={"X-API-Key": result["key"]}, cookies={})
    user = middleware.get_current_user(request)
    assert user and user["type"] == "api_key"
    assert user["is_admin"] is False
    assert user["tier"] == "elite"
    assert not middleware.is_admin_user(user)

    request.method = "POST"
    assert middleware.get_current_user(request) is None


def test_expired_api_key_is_rejected_with_sqlite_datetime(api_key_store):
    result = users.create_api_key_for_user(1, "expired")
    with api_key_store() as db:
        row = db.query(database.ApiKey).one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    request = SimpleNamespace(method="GET", headers={"X-API-Key": result["key"]}, cookies={})
    assert middleware.get_current_user(request) is None


def test_api_key_revoke_is_owned_by_the_user(api_key_store):
    result = users.create_api_key_for_user(1, "revoke me")
    with api_key_store() as db:
        key_id = db.query(database.ApiKey).one().id
    assert users.revoke_api_key(key_id, 2)["success"] is False
    assert users.revoke_api_key(key_id, 1)["success"] is True
    request = SimpleNamespace(method="GET", headers={"X-API-Key": result["key"]}, cookies={})
    assert middleware.get_current_user(request) is None
