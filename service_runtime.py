"""Single-instance engine lifecycle; the web application never enables live mode."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from portal_settings import settings

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from database import init_db
    from operator_auth import init_operator_schema

    init_db()
    init_operator_schema()
    from database import initialize_universe

    initialize_universe()
    app.state.engine_status = (
        "disabled"
        if os.getenv("ENGINE_ENABLED", "true").lower() != "true"
        else "starting"
    )
    lock = None
    ws_started = False
    scheduler_started = False
    try:
        if app.state.engine_status != "disabled":
            import fcntl

            lock = Path("database/.engine.lock").open("a")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError(
                    "An engine instance is already running; use exactly one worker"
                )
            from config import cfg

            cfg.PAPER_TRADING = True
            cfg.TRADING_MODE = "paper"
            import runtime_state as rs

            rs.load()
            rs.mark_crash()
            from trade.ws import start_ws
            from alerts.scanner import register_kline_handler

            register_kline_handler()
            await start_ws()
            ws_started = True
            if cfg.is_demo_configured():
                try:
                    from trade.exchange import get_positions

                    await asyncio.wait_for(get_positions(), timeout=30)
                    from trade.reconciler import reconcile_on_startup

                    await asyncio.wait_for(reconcile_on_startup(), timeout=60)
                    from trade.order_journal import unresolved

                    if unresolved():
                        raise RuntimeError(
                            "Unresolved order intents require reconciliation"
                        )
                    from scheduler import start_scheduler

                    start_scheduler()
                    scheduler_started = True
                    app.state.engine_status = "running"
                except Exception:
                    app.state.engine_status = "reconciliation_failed"
                    log.exception(
                        "Paper exchange initialization failed; scheduler remains stopped"
                    )
            else:
                app.state.engine_status = "credentials_required"
            if cfg.ANGELONE_API_KEY and cfg.ANGELONE_CLIENT_ID:
                try:
                    from engines.indian.auth import init_indian_session

                    await asyncio.wait_for(init_indian_session(), timeout=30)
                except Exception:
                    log.warning("Indian-market integration unavailable")
            if cfg.TELEGRAM_TOKEN and cfg.TELEGRAM_CHAT_ID and cfg.WEBHOOK_SECRET:
                from alerts.telegram.client import (
                    register_webhook,
                    register_commands,
                    send,
                )

                await register_webhook()
                await register_commands()
                await send(
                    "*Signal Engine · Service started*\nMode: PAPER\nRuntime: "
                    + app.state.engine_status
                    + "\nUse /health to verify dependencies."
                )
        yield
    finally:
        if scheduler_started:
            from scheduler import stop_scheduler

            stop_scheduler()
        if ws_started:
            from trade.ws import stop_ws

            await stop_ws()
            from trade.exchange import close_exchange

            await close_exchange()
            from trade.monitor import stop_monitor

            stop_monitor()
        if lock:
            import runtime_state as rs

            rs.mark_clean_shutdown()
            lock.close()
