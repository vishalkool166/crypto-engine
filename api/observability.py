"""Administrator-only, process-local HTTP metrics endpoint."""
from fastapi import APIRouter, Request

from observability import request_metrics

router = APIRouter()


@router.get('/system/metrics', tags=['health'])
async def system_metrics(request: Request):
    from saas.security import require_admin_access
    require_admin_access(request)
    return request_metrics.snapshot()
