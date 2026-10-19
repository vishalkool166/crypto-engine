"""Queries over synthetic records: no broker access or production database."""
import ast
import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import User, AuditLog
import saas.users as user_service

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db_provider(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "pagination-test.db"}')
    User.__table__.create(engine)
    AuditLog.__table__.create(engine)
    Session = sessionmaker(bind=engine)

    @contextmanager
    def session():
        s = Session()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()
    try:
        yield session
    finally:
        engine.dispose()


def admin_audit_endpoint(db_provider):
    """Load only the real route body; authentication imports require unavailable pyotp."""
    source = ast.parse((ROOT/'saas/admin.py').read_text())
    node = next(n for n in source.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'admin_audit')
    node.decorator_list = []
    space = dict(_auth=lambda _: {'tier': 'admin'}, get_session=db_provider,
                 AuditLog=AuditLog, HTTPException=HTTPException, JSONResponse=JSONResponse, Query=Query, Request=Request)
    from sqlalchemy import or_, func
    space.update(or_=or_, func=func, log=__import__('logging').getLogger(__name__))
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<admin endpoint>', 'exec'), space)
    return space['admin_audit']


def test_user_search_filters_before_count_and_pagination(monkeypatch, db_provider):
    monkeypatch.setattr(user_service, 'get_session', db_provider)
    with db_provider() as s:
        for email, name, tier in [
            ('alice@example.test','Alice North','pro'),
            ('bob@example.test','Bob','free'),
            ('another@example.test','ALICE South','pro'),
            ('hello@example.test','Jo','free'),
        ]:
            s.add(User(email=email, name=name, tier=tier))
    first = user_service.list_all_users(limit=1, offset=0, search='alice', tier='pro')
    next_page = user_service.list_all_users(limit=1, offset=1, search='Alice', tier='pro')
    assert first['total'] == next_page['total'] == 2
    assert first['users'][0]['id'] != next_page['users'][0]['id']
    assert user_service.list_all_users(limit=20, search='%')['total'] == 0
    assert user_service.list_all_users(limit=20, search='EXAMPLE.TEST')['total'] == 4
    with pytest.raises(ValueError):
        user_service.list_all_users(limit=200)
    with pytest.raises(ValueError):
        user_service.list_all_users(limit=20, offset=-1)


def test_audit_filters_applied_before_count(db_provider):
    with db_provider() as s:
        for action, detail, ok in [
            ('oauth_login', 'alice session', True),
            ('oauth_login', 'bob session', False),
            ('coin_add', 'Alice coin', True),
            ('mode_toggle', 'pro action', True),
        ]:
            s.add(AuditLog(action=action, source='test', detail=detail, ip='127.0.0.1', success=ok))
    endpoint = admin_audit_endpoint(db_provider)
    async def request(limit=1, offset=0, search='', actions='', success=None):
        return await endpoint(object(),limit,offset,search,actions,success)
    import json
    first = json.loads(asyncio.run(request(search='alice', success=True)).body)
    second = json.loads(asyncio.run(request(offset=1, search='alice', success=True)).body)
    assert first['total'] == second['total'] == 2
    assert first['logs'][0]['id'] != second['logs'][0]['id']
    only = json.loads(asyncio.run(request(limit=10, actions='oauth_login', success=False)).body)
    assert only['total'] == 1 and only['logs'][0]['action'] == 'oauth_login'
    escaped = json.loads(asyncio.run(request(search='%')).body)
    assert escaped['total'] == 0
    with pytest.raises(HTTPException) as raised:
        asyncio.run(request(actions=','))
    assert raised.value.status_code == 422
