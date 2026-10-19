import pytest
from unittest.mock import patch, MagicMock
from saas.security_email import (send_security_email, SecurityEmailType, DeliveryUnavailable)


def test_disallowed_trading_email_rejected_even_when_enabled(monkeypatch):
    monkeypatch.setenv('SECURITY_EMAIL_ENABLED','true')
    monkeypatch.setenv('RESEND_API_KEY','dummy')
    monkeypatch.setenv('SECURITY_EMAIL_FROM','accounts@example.org')
    with patch('httpx.Client') as transport:
        with pytest.raises(ValueError):
            send_security_email(to='user@example.org',kind='trade_opened',message='opened')
        transport.assert_not_called()


def test_disabled_email_fails_closed(monkeypatch):
    monkeypatch.delenv('SECURITY_EMAIL_ENABLED',raising=False)
    with pytest.raises(DeliveryUnavailable):
        send_security_email(to='user@example.org', kind=SecurityEmailType.SECURITY_ALERT, message='New login')


def test_invalid_recipient_is_blocked(monkeypatch):
    with pytest.raises(ValueError):
        send_security_email(to='bad@example.org\r\nBcc: evil@example.org',kind=SecurityEmailType.VERIFY_EMAIL,message='Verify')


def test_successful_security_delivery_escapes_html(monkeypatch):
    monkeypatch.setenv('SECURITY_EMAIL_ENABLED','true')
    monkeypatch.setenv('RESEND_API_KEY','test-value')
    monkeypatch.setenv('SECURITY_EMAIL_FROM','accounts@example.org')
    response = MagicMock(); response.json.return_value={'id':'em_1'}
    with patch('httpx.Client') as mock_cls:
        mock_cls.return_value.__enter__.return_value.post.return_value = response
        result=send_security_email(to='user@example.org',kind=SecurityEmailType.VERIFY_EMAIL,message='<script>alert(1)</script>')
        assert result=='em_1'
        payload=mock_cls.return_value.__enter__.return_value.post.call_args.kwargs['json']
        assert payload['subject'].startswith('Verify')
        assert '<script>' not in payload['html']
        assert '&lt;script&gt;' in payload['html']


def test_provider_error_does_not_leak_sensitive_response(monkeypatch):
    import httpx
    monkeypatch.setenv('SECURITY_EMAIL_ENABLED','true')
    monkeypatch.setenv('RESEND_API_KEY','secret')
    monkeypatch.setenv('SECURITY_EMAIL_FROM','accounts@example.org')
    with patch('httpx.Client') as mock_cls:
        mock_cls.return_value.__enter__.return_value.post.side_effect = httpx.ConnectError('no connection')
        with pytest.raises(DeliveryUnavailable,match='Provider request failed'):
            send_security_email(to='user@example.org',kind=SecurityEmailType.PASSWORD_CHANGED,message='Updated')
