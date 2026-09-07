import asyncio
import json
import logging
import time
from data.fetcher import fetch_and_store, get_funding_rate
from data.cache import cache
from data.rejection_stats import record_scan, get_total_stats, get_top_rejections
from database import get_session, Signal as SignalModel
from trade.exchange import get_balance
from trade.ws import get_mark_price, on_kline_closed
from config import cfg
from alerts.telegram import send_signal, send_scan_summary

log = logging.getLogger(__name__)

_scan_lock      = asyncio.Lock()
_scan_semaphore = asyncio.Semaphore(3)

_cached_balance:    float = 0.0
_balance_cached_at: float = 0.0
_BALANCE_CACHE_TTL: float = 60.0

_scan_stats: dict = {
    "last_scan_at":    0.0,
    "last_scan_count": 0,
    "last_scan_ms":    0.0,
    "total_scans":     0,
    "total_signals":   0,
}


async def _get_cached_balance() -> float:
    global _cached_balance, _balance_cached_at
    if _cached_balance > 0 and (time.time() - _balance_cached_at) < _BALANCE_CACHE_TTL:
        return _cached_balance
    try:
        b       = await get_balance()
        balance = float(b.get("free", 0))
        if balance > 0:
            _cached_balance    = balance
            _balance_cached_at = time.time()
        return balance
    except Exception as e:
        log.error("_get_cached_balance: %s", e)
        return 0.0


def _get_ticker_from_redis(coin: str) -> dict:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return {"change24": 0.0, "change_pos": True}
        raw = r.get(f"ticker:{coin}USDT")
        if not raw:
            return {"change24": 0.0, "change_pos": True}
        data       = json.loads(raw)
        change_pct = float(data.get("percentage", 0))
        return {
            "change24":   round(change_pct, 4),
            "change_pos": change_pct >= 0,
        }
    except Exception:
        return {"change24": 0.0, "change_pos": True}


def _get_funding_from_redis(coin: str) -> float:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return 0.0
        raw = r.get(f"funding:{coin}USDT")
        if not raw:
            return 0.0
        return float(raw)
    except Exception:
        return 0.0


def _derive_session() -> str:
    from datetime import datetime, timezone
    hour = datetime.now(timezone.utc).hour
    if 8  <= hour < 13: return "London"
    if 13 <= hour < 17: return "London/NY Overlap"
    if 17 <= hour < 21: return "New York"
    if 0  <= hour < 8:  return "Asia"
    return "Off Hours"


def _save_signal(signal: dict) -> int | None:
    if signal.get("grade") not in cfg.MIN_GRADE_TO_TRADE:
        return None
    if signal.get("direction") not in ("LONG", "SHORT"):
        return None
    if not signal.get("entry"):
        return None
    if (signal.get("rr1") or 0) < 2.0:
        return None

    try:
        with get_session() as db:
            existing = db.query(SignalModel).filter(
                SignalModel.coin      == signal["coin"],
                SignalModel.direction == signal["direction"],
                SignalModel.outcome   == "pending",
            ).first()

            if existing:
                from trade.executor import has_open_trade
                if has_open_trade(signal["coin"]):
                    return None
                if (
                    existing.entry and signal.get("entry") and
                    abs(float(existing.entry) - float(signal["entry"])) / float(existing.entry) < 0.005
                ):
                    return existing.id
                existing.outcome = "expired"

            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)

            row = SignalModel(
                coin           = signal["coin"],
                direction      = signal["direction"],
                grade          = signal["grade"],
                score          = signal["score"],
                signal_type    = "MOMENTUM",
                entry          = signal["entry"],
                sl             = signal["sl"],
                tp1            = signal["tp1"],
                tp2            = signal.get("tp2"),
                sl_pct         = signal["sl_pct"],
                risk_amt       = signal["risk_amt"],
                risk_pct       = signal["risk_pct"],
                position       = signal["pos_size"],
                leverage       = str(signal["leverage"]) + "x",
                funding        = 0.0,
                oi_signal      = "",
                outcome        = "pending",
                day_of_week    = now.weekday(),
                hour_of_day    = now.hour,
                system_version = cfg.SYSTEM_VERSION,
                regime         = signal.get("regime", ""),
                session        = signal.get("session", ""),
            )
            db.add(row)
            db.flush()
            db.refresh(row)
            log.info(
                "Signal saved id:%s %s %s grade:%s",
                row.id, signal["coin"], signal["direction"], signal["grade"],
            )
            return row.id
    except Exception as e:
        log.error("_save_signal: %s", e)
        return None


def _write_redis(coin: str, signal: dict, db_id: int) -> None:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return
        r.setex(f"signal:{coin}USDT", 1800, json.dumps({
            "coin":        coin,
            "grade":       signal["grade"],
            "direction":   signal["direction"],
            "entry":       signal["entry"],
            "sl":          signal["sl"],
            "stoploss":    signal["sl"],
            "tp1":         signal["tp1"],
            "tp":          signal["tp1"],
            "score":       signal["score"],
            "signal_id":   db_id,
            "valid_until": time.time() + 1800,
        }))
    except Exception as e:
        log.error("_write_redis %s: %s", coin, e)


async def _execute_trade(coin: str, signal: dict, db_id: int) -> None:
    try:
        from trade.executor import open_position, has_open_trade_or_position
        if await has_open_trade_or_position(coin):
            return

        from database import get_session, Trade as TradeModel
        with get_session() as db:
            pending = db.query(TradeModel).filter(
                TradeModel.coin    == coin,
                TradeModel.state   == "pending",
                TradeModel.outcome == "pending",
            ).first()
            if pending:
                log.info("_execute_trade: %s already has pending trade", coin)
                return

        session = _derive_session()
        regime  = signal.get("regime", "ranging")

        await open_position(
            coin      = coin,
            direction = signal["direction"],
            entry     = float(signal["entry"]),
            sl        = float(signal["sl"]),
            tp        = float(signal["tp1"]),
            stake     = float(signal["stake"]),
            leverage  = int(signal["leverage"]),
            signal_id = db_id,
            grade     = signal["grade"],
            regime    = regime,
            session   = session,
            score     = float(signal["score"]),
            tp2       = float(signal["tp2"]) if signal.get("tp2") else None,
        )
    except Exception as e:
        log.error("_execute_trade %s: %s", coin, e)


async def _analyze_coin(coin: str, balance: float) -> dict | None:
    async with _scan_semaphore:
        try:
            from engines.state import get as get_coin_state, set_watching, set_idle

            df_4h = await fetch_and_store(coin, "4h", limit=300)
            df_1h = await fetch_and_store(coin, "1h", limit=300)

            if df_4h is None or len(df_4h) < 200:
                return None
            if df_1h is None or len(df_1h) < 50:
                return None

            from agents.signal_agent import run as agent_run
            result = await agent_run(
                coin    = coin,
                df_4h   = df_4h,
                df_1h   = df_1h,
                balance = balance,
            )

            ticker  = _get_ticker_from_redis(coin)
            funding = _get_funding_from_redis(coin)
            price   = get_mark_price(coin) or float(df_4h["close"].iloc[-1])

            coin_status = "watching" if result.get("signal") else "idle"

            if result.get("signal"):
                set_watching(coin, {
                    "direction": result["direction"],
                })
            else:
                set_idle(coin)

            cache_entry = {
                "coin":      coin,
                "grade":     result.get("grade", "--") if result.get("signal") else "--",
                "direction": result.get("direction", "--"),
                "score":     result.get("score", 0),
                "state":     coin_status,
                "signal":    result if result.get("signal") else {},
                "regime":    result.get("regime", ""),
                "reason":    result.get("reason", ""),
                "market": {
                    "price":      price,
                    "change24":   ticker["change24"],
                    "change_pos": ticker["change_pos"],
                    "funding":    funding,
                },
                "cached_at":   time.time(),
                "agent_ms":    result.get("agent_ms",    0),
                "agent_steps": result.get("agent_steps", 0),
            }

            cache.set(f"signal_{coin}", cache_entry, ttl=1800)

            if not result.get("signal"):
                return cache_entry

            db_id = _save_signal(result)

            if db_id:
                result["db_id"] = db_id
                _write_redis(coin, result, db_id)

                from ml.version_registry import tag_signal
                tag_signal(db_id)

                session = _derive_session()
                await send_signal(result, coin, result.get("grade", ""), session)
                await _execute_trade(coin, result, db_id)

            return cache_entry

        except Exception as e:
            log.error("_analyze_coin %s: %s", coin, e)
            return None


async def scan_all_coins() -> list:
    async with _scan_lock:
        scan_start = time.time()
        coins      = cfg.COINS
        log.info("Scan started — %s coins", len(coins))

        balance = await _get_cached_balance()
        if balance <= 0:
            log.warning("Scan aborted — zero balance")
            return []

        from engines.state import tick_cooldowns
        tick_cooldowns()

        results = await asyncio.gather(
            *[_analyze_coin(coin, balance) for coin in coins],
            return_exceptions=True,
        )

        valid = [r for r in results if r and not isinstance(r, Exception)]
        valid.sort(key=lambda x: x.get("score", 0), reverse=True)

        scan_ms = round((time.time() - scan_start) * 1000, 1)

        _scan_stats["last_scan_at"]    = time.time()
        _scan_stats["last_scan_count"] = len(valid)
        _scan_stats["last_scan_ms"]    = scan_ms
        _scan_stats["total_scans"]    += 1
        _scan_stats["total_signals"]  += sum(1 for r in valid if r.get("grade") in ("A+", "A"))

        _write_engine_health(valid, scan_ms)

        await send_scan_summary(valid)

        from events import emit
        asyncio.create_task(emit("scan_complete"))

        log.info("Scan complete — %s results in %sms", len(valid), scan_ms)
        return valid


async def scan_single_coin(coin: str) -> dict | None:
    try:
        balance = await _get_cached_balance()
        if balance <= 0:
            return None
        return await _analyze_coin(coin, balance)
    except Exception as e:
        log.error("scan_single_coin %s: %s", coin, e)
        return None


def _write_engine_health(results: list, scan_ms: float) -> None:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return

        regimes         = [x.get("regime", "") for x in results if x.get("regime")]
        dominant_regime = max(set(regimes), key=regimes.count) if regimes else "Unknown"
        scores          = [x.get("score", 0) for x in results if x.get("score", 0) > 0]
        avg_score       = round(sum(scores) / len(scores), 1) if scores else 0.0
        top_rejections  = get_top_rejections(3)

        health = {
            "coins_scanned":   len(results),
            "signals_today":   _scan_stats["total_signals"],
            "total_scans":     _scan_stats["total_scans"],
            "avg_scan_ms":     scan_ms,
            "avg_score":       avg_score,
            "dominant_regime": dominant_regime,
            "top_rejections":  top_rejections,
            "signal_rate":     get_total_stats().get("signal_rate", 0),
            "updated_at":      time.time(),
        }

        r.setex("engine:health", 1800, json.dumps(health))

    except Exception as e:
        log.error("_write_engine_health: %s", e)


def _write_active_pairs() -> None:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return
        pairs = [f"{c}/USDT:USDT" for c in cfg.COINS]
        r.setex("pairs:active", 1800, json.dumps({
            "pairs":          pairs,
            "refresh_period": 1800,
        }))
    except Exception:
        pass


def get_db_stats() -> dict:
    try:
        with get_session() as db:
            all_sigs = db.query(SignalModel).all()
            closed   = [s for s in all_sigs if s.outcome in ("win", "loss")]
            wins     = [s for s in closed if s.outcome == "win"]
            by_grade = {}
            for g in ("A+", "A", "B"):
                gt = [s for s in closed if s.grade == g]
                gw = [s for s in gt    if s.outcome == "win"]
                by_grade[g] = {
                    "total":     len(gt),
                    "wins":      len(gw),
                    "losses":    len(gt) - len(gw),
                    "win_rate":  round(len(gw) / len(gt) * 100, 1) if gt else 0,
                    "total_pnl": round(sum(s.pnl or 0 for s in gt), 2),
                }
            return {
                "total":     len(all_sigs),
                "closed":    len(closed),
                "pending":   len(all_sigs) - len(closed),
                "wins":      len(wins),
                "losses":    len(closed) - len(wins),
                "win_rate":  round(len(wins) / len(closed) * 100, 1) if closed else 0,
                "total_pnl": round(sum(s.pnl or 0 for s in closed), 2),
                "by_grade":  by_grade,
            }
    except Exception as e:
        log.error("get_db_stats: %s", e)
        return {}


def get_engine_health() -> dict:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return {}
        raw = r.get("engine:health")
        if not raw:
            return {}
        return json.loads(raw)
    except Exception as e:
        log.error("get_engine_health: %s", e)
        return {}


def get_scan_stats() -> dict:
    return dict(_scan_stats)


def register_kline_handler() -> None:
    on_kline_closed(_on_kline_closed)


async def _on_kline_closed(coin: str, kline: dict) -> None:
    try:
        if kline.get("tf") != "1h":
            return
        from engines.state import get as get_coin_state
        current = get_coin_state(coin)
        if current["status"] not in ("watching", "idle"):
            return
        balance = await _get_cached_balance()
        if balance <= 0:
            return
        await _analyze_coin(coin, balance)
    except Exception as e:
        log.error("_on_kline_closed %s: %s", coin, e)