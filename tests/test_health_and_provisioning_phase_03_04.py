"""Phase 03/04: reproduce the liveness mismatch and validate SaaS identity rules.

Tests use an isolated SQLite DB. They never contact Redis, AWS, exchanges or
real accounts and never start the scheduler.
"""
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
from config import TIER_FREE, TIER_PRO, TIER_ELITE, get_tier_features
from saas import users
from saas.tiers import get_pricing_data

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated_accounts(monkeypatch):
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    database.Base.metadata.create_all(engine, tables=[database.User.__table__, database.Subscription.__table__])
    session_maker = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def session():
        db = session_maker()
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    monkeypatch.setattr(users, 'get_session', session)
    yield session
    engine.dispose()


def test_google_provision_normalizes_email_and_creates_subscription(isolated_accounts):
    result = users.create_or_get_user('  NewUser@Example.TEST ', provider_id='google-sub-1')
    assert result['is_new'] and result['tier'] == TIER_FREE
    with isolated_accounts() as db:
        assert db.query(database.User).count() == 1
        user = db.query(database.User).one()
        assert user.email == 'newuser@example.test'
        sub = db.query(database.Subscription).filter_by(user_id=user.id).one()
        assert sub.status == 'active' and sub.tier == TIER_FREE
    repeat = users.create_or_get_user('newuser@example.test', provider_id='google-sub-1')
    assert not repeat['is_new'] and repeat['id'] == result['id']
    with isolated_accounts() as db:
        assert db.query(database.Subscription).count() == 1


def test_google_provision_repairs_only_missing_legacy_subscription(isolated_accounts):
    with isolated_accounts() as db:
        db.add(database.User(email='legacy@example.test', provider='google', provider_id='legacy-1',
                             tier=TIER_PRO, is_active=True, is_admin=False))
    user = users.create_or_get_user('legacy@example.test', provider_id='legacy-1')
    assert user['tier'] == TIER_PRO
    with isolated_accounts() as db:
        sub = db.query(database.Subscription).one()
        assert sub.tier == TIER_PRO



def test_legacy_mixed_case_email_keeps_existing_google_account(isolated_accounts):
    with isolated_accounts() as db:
        db.add(database.User(email='Existing@Example.TEST', provider='google', provider_id='same-sub',
                             tier=TIER_PRO, is_active=True))
    result = users.create_or_get_user('existing@example.test', provider_id='same-sub')
    assert not result['is_new'] and result['tier'] == TIER_PRO
    with isolated_accounts() as db:
        assert db.query(database.User).count() == 1
        assert db.query(database.Subscription).count() == 1

def test_google_provision_rejects_deactivated_or_unlinked_identity(isolated_accounts):
    with isolated_accounts() as db:
        db.add(database.User(email='disabled@example.test', provider='google', provider_id='sub-a', is_active=False))
        db.add(database.User(email='email@example.test', provider='email', provider_id='local-1', is_active=True))
    with pytest.raises(PermissionError, match='disabled'):
        users.create_or_get_user('disabled@example.test', provider_id='sub-a')
    with pytest.raises(PermissionError, match='linking'):
        users.create_or_get_user('email@example.test', provider_id='google-sub')
    with pytest.raises(PermissionError, match='disabled'):
        users.create_or_get_user('disabled@example.test', provider_id='wrong-google-sub')
    with pytest.raises(ValueError, match='subject'):
        users.create_or_get_user('someone@example.test', provider_id='')


def test_tier_update_preserves_provisioning_and_rejects_unknown_tier(isolated_accounts):
    created = users.create_or_get_user('tier@example.test', provider_id='tier-1')
    assert not users.update_user_tier(created['id'], 'super-admin')['success']
    assert users.update_user_tier(created['id'], TIER_ELITE)['success']
    with isolated_accounts() as db:
        assert db.query(database.User).one().tier == TIER_ELITE
        assert db.query(database.Subscription).one().tier == TIER_ELITE


def test_pricing_catalogue_matches_engine_entitlements():
    catalogue = get_pricing_data()
    assert [p['id'] for p in catalogue['tiers']] == ['free', 'pro', 'elite']
    free = catalogue['tiers'][0]
    assert f'{get_tier_features(TIER_FREE)["signal_delay_minutes"]} minutes' in free['features'][0]['text']
    rows = {r['feature']: r for r in catalogue['comparison']}
    assert rows['Entry / SL / TP']['free_bool'] is False
    assert rows['Entry / SL / TP']['pro_bool'] is True
    assert rows['ML probability']['elite_bool'] is True
    assert rows['Signal delay']['free'] == f'{get_tier_features(TIER_FREE)["signal_delay_minutes"]} min'
    assert all('email support' not in str(row).lower() for row in catalogue['comparison'])


def test_health_routes_have_distinct_responsibilities():
    source = (ROOT / 'api/routes.py').read_text()
    main = (ROOT / 'main.py').read_text()
    endpoints = (ROOT / 'dashboard/src/lib/endpoints.ts').read_text()
    assert '@router.get("/system/health")' in source
    health_body = source.split('async def health(request: Request):', 1)[1].split('\n\n@router.', 1)[0]
    assert health_body.index('require_admin_access(request)') < health_body.index('if _health_cache')
    assert '@app.get("/api/health", include_in_schema=False)' in main
    assert "api.get('/api/system/health')" in endpoints
    assert 'redis_connected' in health_body
    # Prevent the frontend from treating a missing field as a failed Redis probe.
    assert "health?.redis_connected    ?? false" not in (ROOT / 'dashboard/src/hooks/useHealth.ts').read_text()

@pytest.mark.asyncio
async def test_admin_health_does_not_serve_cached_diagnostics_to_anonymous(monkeypatch):
    """Even a warm status cache must not bypass administrator permission checks."""
    import ast
    import time
    import sys
    from types import ModuleType
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse

    parsed = ast.parse((ROOT / 'api/routes.py').read_text())
    health_node = next(node for node in parsed.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'health')
    health_node.decorator_list = []
    scope = {'time': time, '_health_cache': {'data': {'status': 'ok', 'redis_connected': True}, 'at': time.time()},
             'JSONResponse': JSONResponse, 'Request': Request}
    exec(compile(ast.Module(body=[health_node], type_ignores=[]), '<isolated-health>', 'exec'), scope)

    def reject(request):
        raise HTTPException(status_code=403, detail='Administrator required')

    fake_security = ModuleType('saas.security')
    fake_security.require_admin_access = reject
    monkeypatch.setitem(sys.modules, 'saas.security', fake_security)
    with pytest.raises(HTTPException) as error:
        await scope['health'](object())
    assert error.value.status_code == 403

    fake_security.require_admin_access = lambda request: {'is_admin': True}
    response = await scope['health'](object())
    assert response.status_code == 200
    assert b'"redis_connected":true' in response.body
