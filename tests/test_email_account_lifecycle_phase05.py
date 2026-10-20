"""Email account lifecycle regression tests using disposable in-memory SQLite."""
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
from saas import email_accounts as accounts


@pytest.fixture
def isolated(monkeypatch):
    db_engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    tables = [database.User.__table__, database.Subscription.__table__, database.UserSession.__table__,
              accounts.EmailCredential.__table__, accounts.EmailChallenge.__table__, accounts.EmailThrottle.__table__]
    database.Base.metadata.create_all(db_engine, tables=tables)
    maker = sessionmaker(bind=db_engine, expire_on_commit=False)

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

    sent = []
    def capture(*, to, kind, message, **kw):
        sent.append((to, kind, message))
        return 'provider-test-id'

    monkeypatch.setattr(accounts, 'get_session', session)
    monkeypatch.setattr(accounts, 'enabled', lambda: True)
    monkeypatch.setattr(accounts, 'send_security_email', capture)
    monkeypatch.setenv('FRONTEND_URL', 'https://app.vishalkool.top')
    yield session, sent
    db_engine.dispose()


def token_from_email(message):
    token = re.search(r'#token=([0-9a-f]{64})', message)
    assert token, message
    return token.group(1)


def signup(session, sent, email='test@example.org', password='A sample long password 2026!'):
    assert 'email' in accounts.request_registration(email, password, '127.0.0.1')
    token = token_from_email(sent[-1][2])
    assert accounts.verify_registration(token)
    return token


def test_registration_is_pending_until_verified_and_single_use(isolated):
    session, sent = isolated
    accounts.request_registration('  TEST@EXAMPLE.ORG ', 'A sample long password 2026!', '127.0.0.1')
    with session() as db:
        assert db.query(database.User).count() == 0
        pending = db.query(accounts.EmailChallenge).one()
        assert pending.digest != token_from_email(sent[-1][2])
        assert pending.pending_password_digest.startswith('scrypt$')
    token = token_from_email(sent[-1][2])
    assert accounts.verify_registration(token)
    with pytest.raises(accounts.InvalidChallenge):
        accounts.verify_registration(token)
    with session() as db:
        user = db.query(database.User).one()
        assert user.email == 'test@example.org' and user.provider == 'email'
        assert user.tier == 'free' and user.is_admin is False
        assert db.query(database.Subscription).one().tier == 'free'
        assert db.query(accounts.EmailCredential).count() == 1
        assert db.query(accounts.EmailChallenge).one().pending_password_digest is None


def test_google_email_is_not_auto_linked_or_replaced(isolated):
    session, sent = isolated
    with session() as db:
        db.add(database.User(email='test@example.org', provider='google', provider_id='google-123', is_admin=True))
    assert accounts.request_registration('TEST@example.org', 'A sample long password 2026!', '1.2.3.4') == accounts.ACCOUNT_MESSAGE
    assert not sent
    assert accounts.authenticate('test@example.org', 'A sample long password 2026!', '1.2.3.4') is None
    with session() as db:
        assert db.query(database.User).one().provider == 'google'


def test_reset_token_expiry_single_use_and_session_revocation(isolated):
    session, sent = isolated
    signup(session, sent)
    account = accounts.authenticate('test@example.org', 'A sample long password 2026!', '10.0.0.1')
    assert account and account['is_admin'] is False
    with session() as db:
        db.add(database.UserSession(user_id=account['id'], session_id='live-session-id', is_active=True))
    assert accounts.request_password_reset('test@example.org', '10.0.0.2') == accounts.ACCOUNT_MESSAGE
    reset_token = token_from_email(sent[-1][2])
    with session() as db:
        reset_challenge = db.query(accounts.EmailChallenge).filter_by(purpose='reset').one()
        assert reset_challenge.digest != reset_token
    assert accounts.reset_password(reset_token, 'My much better password 2026!')
    assert accounts.authenticate('test@example.org', 'My much better password 2026!', '10.0.0.3') is not None
    assert accounts.authenticate('test@example.org', 'A sample long password 2026!', '10.0.0.4') is None
    with session() as db:
        assert db.query(database.UserSession).one().is_active is False
    with pytest.raises(accounts.InvalidChallenge):
        accounts.reset_password(reset_token, 'Some other new password')


def test_expired_registration_cannot_create_account(isolated):
    session, sent = isolated
    accounts.request_registration('test@example.org', 'A sample long password 2026!', '10.0.0.1')
    token = token_from_email(sent[-1][2])
    with session() as db:
        challenge = db.query(accounts.EmailChallenge).one()
        challenge.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    with pytest.raises(accounts.InvalidChallenge):
        accounts.verify_registration(token)
    with session() as db:
        assert db.query(database.User).count() == 0


def test_email_registration_never_promotes_configured_admin_email(isolated, monkeypatch):
    from config import cfg
    monkeypatch.setattr(cfg, 'is_admin_email', lambda e: True)
    session, sent = isolated
    signup(session, sent)
    with session() as db:
        assert db.query(database.User).one().is_admin is False


def test_rate_limit_enforced_and_no_account_enumeration(isolated):
    session, sent = isolated
    with session() as db:
        db.add(database.User(email='known@example.org', provider='google', provider_id='google-sub'))
    assert accounts.request_password_reset('known@example.org', '10.0.0.1') == accounts.ACCOUNT_MESSAGE
    assert accounts.request_password_reset('unknown@example.org', '10.0.0.2') == accounts.ACCOUNT_MESSAGE
    assert not sent
    for _ in range(4):
        accounts.request_password_reset('unknown@example.org', '10.0.0.2')
    with pytest.raises(accounts.Throttled):
        accounts.request_password_reset('unknown@example.org', '10.0.0.2')


def test_password_validation_and_hash_roundtrip():
    with pytest.raises(ValueError):
        accounts.hash_password('short')
    digest = accounts.hash_password('Long enough password for account')
    assert 'Long enough password for account' not in digest
    assert accounts.matches_password('Long enough password for account', digest)
    assert not accounts.matches_password('wrong passphrase', digest)
    assert not accounts.matches_password('Long enough password for account', 'invalid')


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv('EMAIL_ACCOUNTS_ENABLED', raising=False)
    monkeypatch.delenv('SECURITY_EMAIL_ENABLED', raising=False)
    assert not accounts.enabled()


def test_async_delivery_callback_and_email_input_validation(isolated):
    session, sent = isolated
    queued = []
    result = accounts.request_registration('test@example.org', 'A sample long password 2026!',
                                           '127.0.0.1', dispatch=lambda **kwargs: queued.append(kwargs))
    assert result == accounts.ACCOUNT_MESSAGE
    assert not sent and len(queued) == 1
    assert queued[0]['kind'] == accounts.SecurityEmailType.VERIFY_EMAIL
    for invalid in ('a,b@example.org', 'Test <test@example.org>', 'something@example.org\nBCC:evil@example.org'):
        with pytest.raises(ValueError):
            accounts.normalize_email(invalid)
