from saas.origin_security import allowed_request_origin, canonical_origin


def test_valid_same_site_origins():
    trusted = ['https://app.example.test', 'https://api.example.test', 'http://localhost:5173']
    assert allowed_request_origin('https://app.example.test', trusted)
    assert allowed_request_origin('https://API.example.test/', trusted)
    assert allowed_request_origin('http://localhost:5173', trusted)


def test_rejects_cross_site_and_ambiguous_origins():
    trusted = ['https://app.example.test']
    for bad in (None, '', 'null', 'https://app.example.test.attacker.test',
                'https://app.example.test@evil.test',
                'https://app.example.test/path', 'https://app.example.test?next=x',
                'javascript://app.example.test', 'http://app.example.test',
                'https://app.example.test:9443'):
        assert not allowed_request_origin(bad, trusted), bad


def test_default_port_normalization():
    assert canonical_origin('https://api.example.test:443') == 'https://api.example.test'
    assert canonical_origin('http://localhost:80') == 'http://localhost'
