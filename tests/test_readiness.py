"""Readiness distinguishes process liveness from DB/Redis dependency state."""
import asyncio
import sys
from types import ModuleType

from fastapi.responses import JSONResponse

from saas.readiness import readiness_status
from test_security_regression import extracted_function


def test_readiness_reports_ready_only_when_all_dependencies_pass():
    assert readiness_status(lambda: True, lambda: True) == {
        'status': 'ready', 'checks': {'database': 'up', 'redis': 'up'},
    }
    assert readiness_status(lambda: True, lambda: False) == {
        'status': 'degraded', 'checks': {'database': 'up', 'redis': 'down'},
    }


def test_readiness_sanitizes_dependency_exceptions():
    def fail():
        raise RuntimeError('private connection details')
    result = readiness_status(fail, lambda: True)
    assert result == {'status': 'degraded', 'checks': {'database': 'down', 'redis': 'up'}}
    assert 'private connection details' not in str(result)


def test_http_readiness_maps_dependency_state_to_status_code(monkeypatch):
    module = ModuleType('saas.readiness')
    module.readiness_status = lambda: {'status': 'degraded', 'checks': {'database': 'down', 'redis': 'up'}}
    monkeypatch.setitem(sys.modules, 'saas.readiness', module)
    handler = extracted_function('main.py', 'api_readiness', {'JSONResponse': JSONResponse})
    response = asyncio.run(handler())
    assert response.status_code == 503
