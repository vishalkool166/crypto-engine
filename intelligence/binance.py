"""Binance public futures intelligence. No Hyperliquid, no exchange credentials.

Public aggregate futures data is NOT a window into private trader accounts.
Null is returned for unavailable metrics; never fabricate a 50:50 long/short.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import math
import time
import httpx
from config import COIN_CONFIG

_PUBLIC = "https://fapi.binance.com"
_CACHE: dict[str, tuple[float,dict]] = {}
_LIFETIME = 150


def safe_float(obj, key):
    try:
        value=float(obj[key])
        return value if math.isfinite(value) else None
    except (KeyError,ValueError,TypeError,OverflowError):
        return None


async def overview(coin: str) -> dict:
    coin=coin.upper().strip()
    if coin not in COIN_CONFIG:
        raise ValueError("Unknown configured coin")
    cached=_CACHE.get(coin)
    if cached and (time.monotonic()-cached[0]) < _LIFETIME:
        return cached[1]
    symbol=coin+"USDT"
    sources={
        "premium":("/fapi/v1/premiumIndex",{"symbol":symbol}),
        "open_interest":("/fapi/v1/openInterest",{"symbol":symbol}),
        "long_short":("/futures/data/globalLongShortAccountRatio",{"symbol":symbol,"period":"1h","limit":2}),
        "top_traders":("/futures/data/topLongShortAccountRatio",{"symbol":symbol,"period":"1h","limit":2}),
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(7), follow_redirects=False) as client:
        async def get(name, query):
            path,params=query
            try:
                r=await client.get(_PUBLIC+path,params=params)
                r.raise_for_status()
                payload=r.json()
                if isinstance(payload,dict) and "code" in payload and "msg" in payload:
                    return name,None,"exchange_error"
                if not payload or not isinstance(payload,(dict,list)):
                    return name,None,"empty_or_malformed_payload"
                return name,payload,None
            except (httpx.HTTPError,ValueError) as exc:
                return name,None,type(exc).__name__
        received=await asyncio.gather(*(get(k,q) for k,q in sources.items()))
    results={name:(data,error) for name,data,error in received}
    premium=results["premium"][0] or {}
    oi=results["open_interest"][0] or {}
    ls=results["long_short"][0] or []
    top=results["top_traders"][0] or []
    ls_latest=ls[-1] if isinstance(ls,list) and ls else {}
    top_latest=top[-1] if isinstance(top,list) and top else {}
    out={"coin":coin,"market":"Binance USDT-M perpetual futures","observed_at":datetime.now(timezone.utc).isoformat(),"public_aggregates_only":True,"auto_copy_trading":False,"funding_rate":safe_float(premium,"lastFundingRate"),"mark_price":safe_float(premium,"markPrice"),"open_interest_contracts":safe_float(oi,"openInterest"),"global_long_short_ratio":safe_float(ls_latest,"longShortRatio"),"top_account_long_short_ratio":safe_float(top_latest,"longShortRatio"),"source_timestamps_ms":{"premium":premium.get("time") if isinstance(premium,dict) else None,"open_interest":oi.get("time") if isinstance(oi,dict) else None,"long_short":ls_latest.get("timestamp") if isinstance(ls_latest,dict) else None,"top_traders":top_latest.get("timestamp") if isinstance(top_latest,dict) else None},"data_status":{k:("available" if v[0] is not None else "unavailable: "+str(v[1])) for k,v in results.items()},"notes":["Aggregated public account ratios are NOT confirmed profitable-trader positions","Top-account ratios represent an exchange-defined subset, not identified wallets","Data sources can be delayed or inaccessible in some regions"]}
    _CACHE[coin]=(time.monotonic(),out)
    return out
