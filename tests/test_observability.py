from observability import RequestMetrics, request_id, route_template


def test_request_id_rejects_unbounded_or_header_injection_values():
    assert request_id('trace-42_ok') == 'trace-42_ok'
    assert request_id('bad value\r\nX-Evil: yes') != 'bad value\r\nX-Evil: yes'
    assert len(request_id('x' * 65)) == 32


def test_metrics_use_bounded_route_templates_and_status_classes():
    metrics = RequestMetrics()
    metrics.record('GET', '/api/users/{user_id}', 200, 0.025)
    metrics.record('GET', '/api/users/{user_id}', 503, 0.075)
    result = metrics.snapshot()
    assert result['scope'] == 'this_process_since_start'
    assert result['requests'] == [
        {'method': 'GET', 'route': '/api/users/{user_id}', 'status_class': '2xx', 'count': 1},
        {'method': 'GET', 'route': '/api/users/{user_id}', 'status_class': '5xx', 'count': 1},
    ]
    assert result['latency'] == [{
        'method': 'GET', 'route': '/api/users/{user_id}', 'count': 2,
        'mean_ms': 50.0, 'max_ms': 75.0,
    }]


def test_unmatched_request_does_not_include_raw_url():
    class Request:
        scope = {'path': '/private/account/abc'}

    assert route_template(Request()) == 'unmatched'
