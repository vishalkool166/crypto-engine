import logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def _is_todays_orb(orb: dict) -> bool:
    if not orb:
        return False
    orb_date = orb.get("date", "")
    today    = datetime.now(IST).strftime("%Y-%m-%d")
    return orb_date == today


def _is_data_fresh(max_age_seconds: int = 600) -> bool:
    try:
        from engines.indian.data import get_last_refresh_age
        age = get_last_refresh_age()
        return age < max_age_seconds
    except Exception:
        return False


async def recover_missed_jobs() -> None:
    """
    Called on every container startup.
    Checks what critical Indian market jobs were missed
    and runs them immediately if needed.

    Critical jobs that can be missed on restart:
      1. Session refresh     — 3:30 UTC (9:00 IST)
      2. ORB setup           — 4:05 UTC (9:35 IST)
      3. Data refresh        — every 5 minutes

    This ensures the system is fully operational
    within 60 seconds of any container restart
    regardless of what time the restart happens.
    """
    now         = datetime.now(IST)
    is_weekday  = now.weekday() < 5
    market_open = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    market_close= now.replace(hour=15, minute=30, second=0, microsecond=0)
    orb_ready   = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    in_market   = market_open <= now <= market_close
    orb_window  = orb_ready   <= now <= market_close

    log.info(
        "Indian startup recovery: time=%s weekday=%s in_market=%s orb_window=%s",
        now.strftime("%H:%M IST"),
        is_weekday,
        in_market,
        orb_window,
    )

    if not is_weekday:
        log.info("Indian startup recovery: weekend — nothing to recover")
        return

    if not in_market:
        log.info("Indian startup recovery: market closed — nothing to recover")
        return

    await _ensure_session()
    await _ensure_orb(orb_window)
    await _ensure_fresh_data()

    log.info("Indian startup recovery complete")


async def _ensure_session() -> None:
    try:
        from engines.indian.auth import is_session_valid, refresh_session

        if is_session_valid():
            log.info("Startup recovery: session valid — skipping re-login")
            return

        log.warning("Startup recovery: session invalid — re-logging in")
        api = refresh_session()

        if api:
            log.info("Startup recovery: session restored successfully")
        else:
            log.error("Startup recovery: session restore failed")
            try:
                from alerts.telegram import send
                await send(
                    "🚨 *Indian Market — Startup Recovery Failed*\n\n"
                    "Could not restore AngelOne session on container start.\n"
                    "Indian market signals may be affected.\n\n"
                    "Check credentials in .env"
                )
            except Exception:
                pass

    except Exception as e:
        log.error("Startup recovery _ensure_session: %s", e)


async def _ensure_orb(orb_window: bool) -> None:
    try:
        if not orb_window:
            log.info("Startup recovery: outside ORB window — skipping ORB setup")
            return

        from engines.indian.scanner import get_orb_levels
        from config import cfg

        all_orb_set = True
        for name in cfg.INDIAN_INSTRUMENTS:
            orb = get_orb_levels(name)
            if not _is_todays_orb(orb):
                all_orb_set = False
                log.warning(
                    "Startup recovery: %s ORB missing or stale — running setup",
                    name
                )
                break

        if all_orb_set:
            log.info("Startup recovery: ORB already set for today — skipping")
            return

        log.info("Startup recovery: running ORB setup now")

        from engines.indian.scanner import setup_orb
        from engines.indian.instruments import get_instruments
        from engines.indian.strategy import MIN_ORB_SIZE, MAX_ORB_SIZE
        from alerts.telegram import send

        result = setup_orb()

        if not result:
            log.error("Startup recovery: ORB setup returned no data")
            await send(
                "⚠️ *Indian Market — ORB Setup Failed*\n\n"
                "Container restarted during market hours.\n"
                "ORB setup ran but returned no data.\n"
                "Check AngelOne connection."
            )
            return

        instruments = get_instruments()
        lines       = ["🔄 *Indian Market — Startup Recovery*\n"]
        lines.append("Container restarted — ORB recovered:\n")

        for name, orb in result.items():
            orb_size  = orb.get("size", 0)
            orb_ok    = MIN_ORB_SIZE <= orb_size <= MAX_ORB_SIZE
            orb_emoji = "✅" if orb_ok else "❌"
            lines.append(
                f"{orb_emoji} *{name}*\n"
                f"High: `{orb['high']:.2f}` "
                f"Low: `{orb['low']:.2f}` "
                f"Range: `{orb_size:.0f} pts`"
            )

        await send("\n".join(lines))
        log.info("Startup recovery: ORB setup complete — %s instruments", len(result))

    except Exception as e:
        log.error("Startup recovery _ensure_orb: %s", e)


async def _ensure_fresh_data() -> None:
    try:
        if _is_data_fresh(max_age_seconds=600):
            log.info("Startup recovery: data is fresh — skipping refresh")
            return

        log.info("Startup recovery: data stale — refreshing now")

        from engines.indian.data import refresh_indian_data, _is_rate_limited
        from engines.indian.instruments import get_instruments
        from config import cfg

        if _is_rate_limited():
            log.warning("Startup recovery: rate limited — skipping data refresh")
            return

        instruments = get_instruments()
        for name in cfg.INDIAN_INSTRUMENTS:
            inst = instruments.get(name)
            if not inst:
                continue

            result = refresh_indian_data(inst["token"], name)

            if result.get("success"):
                log.info(
                    "Startup recovery: %s refreshed ltp=%.2f range=%.2f",
                    name,
                    result.get("ltp",       0),
                    result.get("day_range", 0),
                )
            elif result.get("rate_limited"):
                log.warning("Startup recovery: rate limited during data refresh")
                break
            else:
                log.warning("Startup recovery: data refresh failed for %s", name)

    except Exception as e:
        log.error("Startup recovery _ensure_fresh_data: %s", e)


async def get_startup_status() -> dict:
    """
    Returns current status of Indian market components.
    Useful for debugging and health checks.
    """
    try:
        from engines.indian.auth import is_session_valid, get_session_age_hours
        from engines.indian.data import (
            get_last_refresh_age, _is_rate_limited,
            get_ltp_from_redis, get_day_range_from_redis,
        )
        from engines.indian.scanner import get_orb_levels
        from engines.indian.instruments import get_instruments
        from config import cfg

        now         = datetime.now(IST)
        instruments = get_instruments()

        instrument_status = {}
        for name in cfg.INDIAN_INSTRUMENTS:
            inst      = instruments.get(name)
            token     = inst["token"] if inst else None
            orb       = get_orb_levels(name)
            ltp       = get_ltp_from_redis(token)       if token else None
            day_range = get_day_range_from_redis(token) if token else 0.0

            instrument_status[name] = {
                "token":         token,
                "ltp":           ltp,
                "day_range":     day_range,
                "orb_set":       _is_todays_orb(orb),
                "orb_date":      orb.get("date") if orb else None,
                "orb_high":      orb.get("high") if orb else None,
                "orb_low":       orb.get("low")  if orb else None,
                "orb_size":      orb.get("size") if orb else None,
            }

        return {
            "time_ist":        now.strftime("%H:%M:%S IST"),
            "market_open":     is_market_open_now(),
            "session_valid":   is_session_valid(),
            "session_age_hrs": get_session_age_hours(),
            "data_age_secs":   get_last_refresh_age(),
            "data_fresh":      _is_data_fresh(),
            "rate_limited":    _is_rate_limited(),
            "instruments":     instrument_status,
        }

    except Exception as e:
        log.error("get_startup_status: %s", e)
        return {"error": str(e)}


def is_market_open_now() -> bool:
    try:
        from engines.indian.data import is_market_open
        return is_market_open()
    except Exception:
        return False