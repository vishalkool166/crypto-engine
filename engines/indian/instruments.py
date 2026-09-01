import logging
import re
import time
import requests
from datetime import datetime
from config import cfg

log = logging.getLogger(__name__)

MASTER_URL   = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
_cache_at    = 0.0
_cache_ttl   = 86400.0
_instruments = {}

MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
    "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8,
    "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _download_master() -> list:
    try:
        r = requests.get(MASTER_URL, timeout=30)
        return r.json()
    except Exception as e:
        log.error("Master contract download failed: %s", e)
        return []


def _parse_expiry(symbol: str, instrument: str) -> datetime | None:
    part = symbol[len(instrument):-3]
    m    = re.match(r"(\d{2})([A-Z]{3})(\d{2})", part)
    if not m:
        return None
    try:
        day = int(m.group(1))
        mon = MONTH_MAP.get(m.group(2), 0)
        yr  = 2000 + int(m.group(3))
        return datetime(yr, mon, day)
    except Exception:
        return None


def _find_nearest(scrips: list, instrument: str) -> dict | None:
    now      = datetime.now()
    best     = None
    best_dt  = None

    for s in scrips:
        if s.get("exch_seg") != "NFO":
            continue
        sym = s.get("symbol", "")
        if not sym.startswith(instrument) or not sym.endswith("FUT"):
            continue
        if any(x in sym for x in ["NXTSO", "FPI", "MIDCAP"]):
            continue

        expiry = _parse_expiry(sym, instrument)
        if not expiry or expiry < now:
            continue

        if best_dt is None or expiry < best_dt:
            best_dt = expiry
            best    = s

    return best


def refresh_instruments() -> dict:
    global _cache_at, _instruments

    scrips = _download_master()
    if not scrips:
        return _instruments

    result = {}
    for name in cfg.INDIAN_INSTRUMENTS:
        s = _find_nearest(scrips, name)
        if s:
            result[name] = {
                "name":     name,
                "symbol":   s.get("symbol"),
                "token":    s.get("token"),
                "exchange": "NFO",
                "lot_size": int(s.get("lotsize", 1)),
                "tick":     float(s.get("tick_size", 0.05)),
            }
            log.info(
                "Instrument: %s symbol=%s token=%s lot=%s",
                name,
                s.get("symbol"),
                s.get("token"),
                s.get("lotsize"),
            )
        else:
            log.warning("Instrument not found: %s", name)

    _instruments = result
    _cache_at    = time.time()
    return _instruments


def get_instruments() -> dict:
    global _cache_at
    if not _instruments or (time.time() - _cache_at) > _cache_ttl:
        refresh_instruments()
    return _instruments


def get_instrument(name: str) -> dict | None:
    return get_instruments().get(name)