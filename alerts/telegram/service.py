"""Inbound Telegram webhook lifecycle, independent of the trading scheduler."""
import asyncio
import logging
import os
import time
import uuid
import httpx
from config import cfg

log = logging.getLogger(__name__)
_task = None
_status = {"transport": "stopped", "connected": False, "last_update_at": None,
           "last_command_at": None, "last_result": None, "last_error": None}


def status():
    return dict(_status)


def record(result, command=None):
    _status["last_update_at"] = time.time()
    _status["last_result"] = result
    if command:
        _status["last_command_at"] = time.time()
        _status["last_command"] = str(command).split()[0][:40]


async def _poll():
    from alerts.telegram.router import handle_update
    from redis_client import get_redis
    token = uuid.uuid4().hex
    base = "https://api.telegram.org/bot" + cfg.TELEGRAM_TOKEN
    initialized = False
    while True:
        redis = get_redis()
        try:
            if redis is None:
                raise RuntimeError("Redis is unavailable")
            # The lease is renewed before each bounded long-poll/command cycle.
            owned = redis.get("telegram:poller")
            if isinstance(owned, bytes):
                owned = owned.decode()
            if owned != token and not redis.set("telegram:poller", token, nx=True, ex=180):
                raise RuntimeError("Another process is consuming this bot; stop the duplicate bot service")
            redis.expire("telegram:poller", 180)
            async with httpx.AsyncClient(timeout=40) as client:
                if not initialized:
                    response = await client.post(base + "/deleteWebhook", json={"drop_pending_updates": False})
                    if not response.json().get("ok"):
                        raise RuntimeError("Telegram could not disable the webhook for polling")
                    from alerts.telegram.client import register_commands
                    await register_commands()
                    initialized = True
                offset = int(redis.get("telegram:poll-offset") or 0)
                response = await client.post(base + "/getUpdates", json={
                    "offset": offset, "timeout": 25, "limit": 10,
                    "allowed_updates": ["message"]})
                result = response.json()
                if not result.get("ok"):
                    raise RuntimeError("Telegram polling rejected; check the bot token and duplicate getUpdates clients")
                _status.update(connected=True, last_error=None)
                for update in result.get("result", []):
                    # Commands are bounded; claim before effects prevents duplicate order/scan actions.
                    await asyncio.wait_for(handle_update(update), timeout=120)
                    redis.set("telegram:poll-offset", int(update["update_id"]) + 1)
                    redis.expire("telegram:poller", 180)
        except asyncio.CancelledError:
            if redis is not None:
                try:
                    redis.eval("if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end", 1, "telegram:poller", token)
                except Exception:
                    pass
            raise
        except Exception as exc:
            # Never log token-bearing request URLs or raw provider exceptions.
            reason = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
            _status.update(connected=False, last_error=reason)
            log.warning("Telegram command transport: %s", reason)
            await asyncio.sleep(5)


async def start():
    global _task
    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
        _status.update(transport="not_configured", last_error="Configure TELEGRAM_TOKEN and TELEGRAM_CHAT_ID")
        return
    transport = os.getenv("TELEGRAM_TRANSPORT", "webhook").lower()
    if transport not in ("polling", "webhook"):
        raise RuntimeError("TELEGRAM_TRANSPORT must be polling or webhook")
    _status["transport"] = transport
    if transport == "polling":
        if _task is None or _task.done():
            _task = asyncio.create_task(_poll(), name="telegram-polling")
    else:
        from alerts.telegram.client import register_webhook, register_commands
        registered = await register_webhook()
        await register_commands()
        _status.update(connected=registered, last_error=None if registered else "Webhook registration failed")


async def stop():
    global _task
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
    _status["connected"] = False
