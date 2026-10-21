"""Google session + CSRF middleware + one-use TOTP for account-mode changes."""
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field
from operator_auth import require_operator
from trade import mode

router = APIRouter()


class ModeChange(BaseModel):
    target: Literal["paper", "live"]
    expected_mode: Literal["paper", "live"]
    totp_code: str = Field(pattern=r"^\d{6}$")
    confirmation: str = Field(max_length=40)


@router.get("/execution/mode")
def execution_mode(request: Request):
    require_operator(request)
    return mode.mode_status()


@router.post("/execution/mode", status_code=202)
async def change_mode(body: ModeChange, request: Request, tasks: BackgroundTasks):
    user = require_operator(request)
    from auth import audit, verify_totp
    from redis_client import get_redis
    redis = get_redis()
    if redis is None:
        raise HTTPException(503, "Step-up verification unavailable")
    import hashlib
    key = "operator:mode-attempts:" + hashlib.sha256(user["email"].encode()).hexdigest()
    try:
        attempts = redis.incr(key)
        if attempts == 1:
            redis.expire(key, 300)
    except Exception:
        raise HTTPException(503, "Step-up verification unavailable") from None
    if attempts > 5:
        raise HTTPException(429, "Too many mode-change attempts; wait five minutes")
    expected = "ENABLE LIVE TRADING" if body.target == "live" else "RETURN TO PAPER"
    if body.confirmation != expected:
        raise HTTPException(400, "Type the exact confirmation shown in the dialog")
    if not verify_totp(body.totp_code):
        audit("execution_mode_denied", user["email"], "Invalid or reused authenticator code", success=False)
        raise HTTPException(401, "Invalid or reused authenticator code")
    try:
        result = await mode.request_transition(body.target, body.expected_mode, user["email"],
            request.headers.get("x-visitor-ip", ""))
    except HTTPException as exc:
        audit("execution_mode_denied", user["email"], str(exc.detail), success=False)
        raise
    request.app.state.engine_status = "switching_mode"
    tasks.add_task(mode.restart_process)
    return result
