import logging
import time
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_rs_cache: dict = {}
_rs_cache_time: float = 0.0
_RS_CACHE_TTL = 900.0


def _get_btc_change() -> float:
    try:
        from redis_client import get_redis
        import json
        r = get_redis()
        if not r:
            return 0.0
        raw = r.get("ticker:BTCUSDT")
        if raw:
            return float(json.loads(raw).get("percentage", 0))
        return 0.0
    except Exception:
        return 0.0


def _get_coin_change(coin: str) -> float:
    try:
        from redis_client import get_redis
        import json
        r = get_redis()
        if not r:
            return 0.0
        raw = r.get(f"ticker:{coin}USDT")
        if raw:
            return float(json.loads(raw).get("percentage", 0))
        return 0.0
    except Exception:
        return 0.0


def _get_coin_volume_ratio(coin: str) -> float:
    try:
        from data.store import load_candles
        df = load_candles(coin, "1h", limit=50)
        if df is None or len(df) < 20:
            return 1.0
        vol_ma = float(df["volume"].rolling(20).mean().iloc[-1])
        cur_vol = float(df["volume"].iloc[-1])
        if vol_ma <= 0:
            return 1.0
        return round(cur_vol / vol_ma, 3)
    except Exception:
        return 1.0


def _get_coin_adx(coin: str) -> float:
    try:
        from data.cache import cache
        cached = cache.get_raw(f"signal_{coin}")
        if cached:
            return float(cached.get("wconf", {}).get("btc_score", 0) or 0)
        from data.store import load_candles
        from engines.indicators import calculate_all
        df = load_candles(coin, "4h", limit=100)
        if df is None or len(df) < 20:
            return 0.0
        d = calculate_all(df, timeframe="4h")
        return float(d.get("adx") or 0)
    except Exception:
        return 0.0


def _get_coin_momentum(coin: str) -> float:
    try:
        from data.store import load_candles
        df = load_candles(coin, "4h", limit=20)
        if df is None or len(df) < 10:
            return 0.0
        closes = df["close"].values
        momentum = (closes[-1] - closes[-10]) / closes[-10] * 100
        return round(float(momentum), 4)
    except Exception:
        return 0.0


def _score_coin(coin: str, btc_change: float) -> dict:
    change = _get_coin_change(coin)
    rs = change - btc_change
    vol_ratio = _get_coin_volume_ratio(coin)
    adx = _get_coin_adx(coin)
    momentum = _get_coin_momentum(coin)

    rs_score = min(max(rs * 2, -20), 20)
    vol_score = min((vol_ratio - 1.0) * 10, 15) if vol_ratio > 1 else max((vol_ratio - 1.0) * 5, -10)
    adx_score = min(adx / 3, 15)
    momentum_score = min(max(momentum * 1.5, -15), 15)

    total = round(rs_score + vol_score + adx_score + momentum_score, 2)

    return {
        "coin":           coin,
        "total_score":    total,
        "rs":             round(rs, 4),
        "rs_score":       round(rs_score, 2),
        "vol_ratio":      vol_ratio,
        "vol_score":      round(vol_score, 2),
        "adx":            round(adx, 2),
        "adx_score":      round(adx_score, 2),
        "momentum":       round(momentum, 4),
        "momentum_score": round(momentum_score, 2),
        "change_24h":     round(change, 4),
        "btc_change":     round(btc_change, 4),
        "tier":           "",
        "scored_at":      time.time(),
    }


def rank_coins(coins: list) -> list:
    global _rs_cache, _rs_cache_time

    now = time.time()
    if _rs_cache and (now - _rs_cache_time) < _RS_CACHE_TTL:
        cached_coins = set(c["coin"] for c in _rs_cache)
        if set(coins) == cached_coins:
            return _rs_cache

    btc_change = _get_btc_change()
    scored = []

    for coin in coins:
        try:
            s = _score_coin(coin, btc_change)
            scored.append(s)
        except Exception as e:
            log.warning("rs rank %s: %s", coin, e)
            scored.append({
                "coin":        coin,
                "total_score": 0.0,
                "tier":        "low",
            })

    scored.sort(key=lambda x: x["total_score"], reverse=True)

    total = len(scored)
    for i, s in enumerate(scored):
        pct = i / total if total > 0 else 0
        if pct < 0.33:
            s["tier"] = "high"
        elif pct < 0.66:
            s["tier"] = "medium"
        else:
            s["tier"] = "low"
        s["rank"] = i + 1

    _rs_cache = scored
    _rs_cache_time = now

    return scored


def get_tier(coin: str, coins: list) -> str:
    ranked = rank_coins(coins)
    for r in ranked:
        if r["coin"] == coin:
            return r.get("tier", "medium")
    return "medium"


def get_rank(coin: str, coins: list) -> int:
    ranked = rank_coins(coins)
    for r in ranked:
        if r["coin"] == coin:
            return r.get("rank", len(coins))
    return len(coins)


def get_scan_priority(coin: str, coins: list) -> dict:
    ranked = rank_coins(coins)
    for r in ranked:
        if r["coin"] == coin:
            tier = r.get("tier", "medium")
            return {
                "coin":       coin,
                "tier":       tier,
                "rank":       r.get("rank", 0),
                "score":      r.get("total_score", 0),
                "deep_scan":  tier in ("high", "medium"),
                "skip_scan":  False,
            }
    return {
        "coin":      coin,
        "tier":      "medium",
        "rank":      len(coins),
        "score":     0.0,
        "deep_scan": True,
        "skip_scan": False,
    }


def get_rs_summary(coins: list) -> dict:
    ranked = rank_coins(coins)
    high = [r for r in ranked if r.get("tier") == "high"]
    medium = [r for r in ranked if r.get("tier") == "medium"]
    low = [r for r in ranked if r.get("tier") == "low"]
    return {
        "total":       len(ranked),
        "high_tier":   len(high),
        "medium_tier": len(medium),
        "low_tier":    len(low),
        "top_5":       ranked[:5],
        "bottom_5":    ranked[-5:],
        "ranked_at":   _rs_cache_time,
    }


def invalidate_cache() -> None:
    global _rs_cache, _rs_cache_time
    _rs_cache = []
    _rs_cache_time = 0.0