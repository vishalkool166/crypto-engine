import logging
import json
import time
from datetime import datetime, timezone, timedelta
from engines.indian.data import (
    is_market_open, is_orb_ready,
    get_orb_candle, get_ltp_live,
    get_ltp_from_redis,
    get_pre_range_from_redis,
    get_prev_range_from_redis,
    fetch_pre_range,
)
from engines.indian.instruments import get_instrument
from engines.indian.strategy import analyze, ENTRY_START_H
from config import cfg

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

_orb_levels:    dict = {}
_signals_today: dict = {}
_last_date:     str  = ""


def _today_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def _reset_if_new_day():
    global _orb_levels, _signals_today, _last_date
    today = _today_ist()
    if today != _last_date:
        _orb_levels    = {}
        _signals_today = {}
        _last_date     = today
        log.info("Indian scanner: new day reset — %s", today)


def setup_orb() -> dict:
    _reset_if_new_day()

    results = {}
    for i, name in enumerate(cfg.INDIAN_INSTRUMENTS):
        if i > 0:
            log.info("Waiting 30s before fetching next instrument ORB...")
            time.sleep(30)

        inst = get_instrument(name)
        if not inst:
            log.warning("Instrument not found: %s", name)
            continue

        orb = get_orb_candle(inst["token"])
        if not orb:
            log.warning("ORB candle not available for %s", name)
            continue

        _orb_levels[name] = {
            "high":   orb["high"],
            "low":    orb["low"],
            "size":   round(orb["high"] - orb["low"], 2),
            "volume": orb["volume"],
            "date":   orb["date"],
        }

        results[name] = _orb_levels[name]
        log.info(
            "ORB set: %s high=%.2f low=%.2f size=%.2f",
            name, orb["high"], orb["low"], orb["high"] - orb["low"],
        )

        try:
            from redis_client import get_redis
            r = get_redis()
            if r:
                r.setex(
                    f"indian:orb:{name}",
                    86400,
                    json.dumps(_orb_levels[name]),
                )
        except Exception:
            pass

    return results


def get_orb_levels(name: str) -> dict | None:
    if name in _orb_levels:
        return _orb_levels[name]
    try:
        from redis_client import get_redis
        r = get_redis()
        if r:
            raw = r.get(f"indian:orb:{name}")
            if raw:
                return json.loads(raw)
    except Exception:
        pass
    return None


def _get_pre_range(token: str) -> float:
    cached = get_pre_range_from_redis(token)
    if cached > 0:
        return cached

    now = datetime.now(IST)
    if ENTRY_START_H <= now.hour < 13:
        return fetch_pre_range(token)

    return 0.0


def _get_prev_range(token: str) -> float:
    return get_prev_range_from_redis(token)


async def scan_all() -> list:
    _reset_if_new_day()

    if not is_orb_ready():
        return []

    results = []

    for name in cfg.INDIAN_INSTRUMENTS:
        if name in _signals_today:
            log.debug("Signal already fired today for %s", name)
            continue

        orb = get_orb_levels(name)
        if not orb:
            log.warning("No ORB levels for %s", name)
            continue

        inst = get_instrument(name)
        if not inst:
            continue

        price = get_ltp_from_redis(inst["token"])
        if not price:
            ltp_data = get_ltp_live(inst["token"])
            price    = ltp_data["ltp"] if ltp_data else None
        if not price:
            log.warning("Could not get LTP for %s", name)
            continue

        now        = datetime.now(IST)
        pre_range  = _get_pre_range(inst["token"])
        prev_range = _get_prev_range(inst["token"])

        signal = analyze(
            instrument     = name,
            orb_high       = orb["high"],
            orb_low        = orb["low"],
            current_price  = price,
            current_hour   = now.hour,
            current_minute = now.minute,
            pre_range      = pre_range,
            prev_range     = prev_range,
        )

        if not signal.signal:
            log.debug("%s: no signal — %s", name, signal.reason)
            continue

        _signals_today[name] = signal
        db_id = _save_signal(signal)

        if db_id:
            await _send_alert(signal, db_id)
            results.append(signal)
            log.info(
                "Indian signal: %s %s entry=%.2f sl=%.2f tp1=%.2f rr=%.2f pre=%.0f prev=%.0f",
                name, signal.direction,
                signal.entry, signal.sl, signal.tp1, signal.rr1,
                signal.pre_range, signal.prev_range,
            )

    return results


def _save_signal(signal) -> int | None:
    try:
        from database import get_session, Signal as SignalModel
        from datetime import datetime, timezone

        with get_session() as db:
            now = datetime.now(timezone.utc)
            row = SignalModel(
                coin          = signal.instrument,
                direction     = signal.direction,
                grade         = "A",
                score         = 75.0,
                signal_type   = "ORB",
                entry         = signal.entry,
                sl            = signal.sl,
                tp1           = signal.tp1,
                tp2           = signal.tp2,
                sl_pct        = round(abs(signal.entry - signal.sl) / signal.entry * 100, 3),
                risk_amt      = 0.0,
                risk_pct      = 0.0,
                position      = 0.0,
                leverage      = "1x",
                sweep_score   = 0.0,
                retest_score  = 0.0,
                disp_score    = 0.0,
                funding       = 0.0,
                oi_signal     = "",
                outcome       = "pending",
                day_of_week   = now.weekday(),
                hour_of_day   = now.hour,
                system_version= cfg.SYSTEM_VERSION,
                market        = "indian",
                instrument    = signal.instrument,
                orb_high      = signal.orb_high,
                orb_low       = signal.orb_low,
                orb_size      = signal.orb_size,
            )
            db.add(row)
            db.flush()
            db.refresh(row)
            log.info("Indian signal saved id:%s %s %s", row.id, signal.instrument, signal.direction)
            return row.id
    except Exception as e:
        log.error("_save_signal error: %s", e)
        return None


async def _send_alert(signal, db_id: int) -> None:
    try:
        from alerts.telegram import send
        ist_time  = datetime.now(IST).strftime("%I:%M %p IST")
        from engines.indian.strategy import get_week_of_month
        week      = get_week_of_month(datetime.now(IST).date())

        await send(
            f"📉 *{signal.instrument} SHORT — ORB Breakdown*\n\n"
            f"Time:       `{ist_time}`\n"
            f"Entry:      `{signal.entry:.2f}`\n"
            f"SL:         `{signal.sl:.2f}` ({signal.sl_pts:.0f}pts)\n"
            f"TP1:        `{signal.tp1:.2f}` ({signal.rr1:.1f}R)\n"
            f"TP2:        `{signal.tp2:.2f}` ({signal.rr2:.1f}R)\n\n"
            f"ORB:        `{signal.orb_low:.2f} — {signal.orb_high:.2f}`\n"
            f"ORB Size:   `{signal.orb_size:.0f} pts`\n"
            f"Pre-range:  `{signal.pre_range:.0f} pts`\n"
            f"Prev-range: `{signal.prev_range:.0f} pts`\n"
            f"Week:       `{week} of month`\n\n"
            f"_Signal #{db_id} — Paper tracking_"
        )
    except Exception as e:
        log.error("_send_alert error: %s", e)


def get_today_signals() -> list:
    return [
        {
            "instrument": s.instrument,
            "direction":  s.direction,
            "entry":      s.entry,
            "sl":         s.sl,
            "tp1":        s.tp1,
            "tp2":        s.tp2,
            "orb_high":   s.orb_high,
            "orb_low":    s.orb_low,
            "orb_size":   s.orb_size,
            "sl_pts":     s.sl_pts,
            "tp_pts":     s.tp_pts,
            "rr1":        s.rr1,
            "pre_range":  s.pre_range,
            "prev_range": s.prev_range,
        }
        for s in _signals_today.values()
    ]