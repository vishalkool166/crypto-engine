"""Manual Indian refresh and quota diagnostics remain administrator-only."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api import indian


@pytest.mark.asyncio
async def test_manual_refresh_rejects_non_admin_before_broker_calls(monkeypatch):
    import saas.security
    monkeypatch.setattr(saas.security, 'require_admin_access',
                        lambda req: (_ for _ in ()).throw(HTTPException(403)))
    with pytest.raises(HTTPException) as exc:
        await indian.indian_refresh(SimpleNamespace())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_quota_diagnostic_rejects_non_admin_before_reading_quota(monkeypatch):
    import saas.security
    monkeypatch.setattr(saas.security, 'require_admin_access',
                        lambda req: (_ for _ in ()).throw(HTTPException(403)))
    with pytest.raises(HTTPException) as exc:
        await indian.indian_quota_status(SimpleNamespace())
    assert exc.value.status_code == 403
