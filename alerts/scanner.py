import asyncio
import json
import logging
import time
from data.fetcher import fetch_and_store
from data.cache import cache
from data.store import save_candles
from engines.signal import run as run_signal
from engines import state
from database import get_session, Signal as SignalModel
from trade.exchange import get_balance
from trade.ws import get_mark_price, on_kline_closed
from config import cfg
from alerts.telegram import send_signal, send_scan_summary

log = logging.getLogger(__name__)

_scan_lock      = asyncio.Lock()
_scan_semaphore = asyncio.Semaphore(3)


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


def _derive_regime(result: dict, coin_status: str) -> str:
    direction = result.get("direction", "")
    sweep     = result.get("sweep") or {}
    zone      = result.get("zone")  or {}

    if coin_status == "in_trade":
        return f"{'Bullish' if direction == 'LONG' else 'Bearish'} — In Trade"

    if result.get("signal"):
        strength = sweep.get("relevance", {}).get("label", "")
        return f"{'Bullish' if direction == 'LONG' else 'Bearish'} — {strength} Sweep"

    if result.get("zone_found") and result.get("sweep_found"):
        return f"{'Bullish' if direction == 'LONG' else 'Bearish'} — Zone Active"

    if result.get("sweep_found"):
        return f"{'Bullish' if direction == 'LONG' else 'Bearish'} — Sweep Detected"

    if direction in ("LONG", "SHORT"):
        return f"{'Bullish' if direction == 'LONG' else 'Bearish'} — Scanning"

    return "Scanning"


def _derive_session() -> str:
    from datetime import datetime, timezone
    hour = datetime.now(timezone.utc).hour
    if 8  <= hour < 13: return "London"
    if 13 <= hour < 17: return "London/NY Overlap"
    if 17 <= hour < 21: return "New York"
    if 0  <= hour < 8:  return "Asia"
    return "Off Hours"


def _build_partial_score(result: dict) -> float:
    sweep_score   = result.get("sweep_score", 0) or 0
    zone_score    = result.get("zone_score",  0) or 0
    trigger_score = result.get("trigger_score", 0) or 0

    if result.get("signal"):
        combined = result.get("score", 0) or 0
        return round(combined * 100)

    if result.get("zone_found") and result.get("sweep_found"):
        partial = sweep_score * 0.40 + zone_score * 0.35
        return round(partial * 100)

    if result.get("sweep_found"):
        return round(sweep_score * 0.40 * 100)

    return 0


async def _load_candles(coin: str) -> dict | None:
    try:
        df_4h  = await fetch_and_store(coin, "4h",  limit=200)
        df_1h  = await fetch_and_store(coin, "1h",  limit=300)
        df_15m = await fetch_and_store(coin, "15m", limit=200)
        return {"4h": df_4h, "1h": df_1h, "15m": df_15m}
    except Exception as e:
        log.error("_load_candles %s: %s", coin, e)
        return None


async def _get_balance() -> float:
    try:
        b = await get_balance()
        return float(b.get("free", 0))
    except Exception as e:
        log.error("_get_balance: %s", e)
        return 0.0


def _save_signal(signal: dict) -> int | None:
    if signal.get("grade") not in cfg.MIN_GRADE_TO_TRADE:
        return None
    if signal.get("direction") not in ("LONG", "SHORT"):
        return None
    if not signal.get("entry"):
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
                existing.outcome = "expired"

            row = SignalModel(
                coin         = signal["coin"],
                direction    = signal["direction"],
                grade        = signal["grade"],
                score        = signal["score"],
                signal_type  = signal["signal_type"],
                entry        = signal["entry"],
                sl           = signal["sl"],
                tp1          = signal["tp1"],
                tp2          = signal.get("tp2"),
                sl_pct       = signal["sl_pct"],
                risk_amt     = signal["risk_amt"],
                risk_pct     = signal["risk_pct"],
                position     = signal["pos_size"],
                leverage     = str(signal["leverage"]) + "x",
                sweep_score  = signal["sweep_score"],
                retest_score = 0,
                disp_score   = signal["trigger_score"],
                funding      = 0,
                oi_signal    = "",
                outcome      = "pending",
                atr_at_entry = signal.get("atr_4h"),
            )
            db.add(row)
            db.flush()
            db.refresh(row)
            log.info("Signal saved ID:%s %s %s grade:%s", row.id, signal["coin"], signal["direction"], signal["grade"])
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
            log.info("_execute_trade: %s already has position", coin)
            return

        result = await open_position(
            coin      = coin,
            direction = signal["direction"],
            entry     = float(signal["entry"]),
            sl        = float(signal["sl"]),
            tp        = float(signal["tp1"]),
            stake     = float(signal["stake"]),
            leverage  = int(signal["leverage"]),
            signal_id = db_id,
            grade     = signal["grade"],
            regime    = "",
            session   = "",
            score     = float(signal["score"]),
            tp2       = float(signal["tp2"]) if signal.get("tp2") else None,
            atr_15m   = float(signal.get("atr_15m", 0)),
        )

        if result.get("success"):
            current_state = state.get(coin)
            state.set_in_trade(coin, result["trade_id"], current_state.get("setup", {}))
            log.info("Trade opened: %s %s grade:%s trade_id:%s",
                     coin, signal["direction"], signal["grade"], result["trade_id"])
        else:
            log.error("Trade open failed %s: %s", coin, result.get("error"))

    except Exception as e:
        log.error("_execute_trade %s: %s", coin, e, exc_info=True)


async def _analyze_coin(coin: str, balance: float) -> dict | None:
    async with _scan_semaphore:
        try:
            current = state.get(coin)

            if current["status"] == "in_trade":
                cached = cache.get_raw(f"signal_{coin}")
                if cached:
                    ticker = _get_ticker_from_redis(coin)
                    cached["market"]["change24"]   = ticker["change24"]
                    cached["market"]["change_pos"] = ticker["change_pos"]
                    cached["market"]["price"]      = get_mark_price(coin) or cached["market"].get("price", 0)
                    cache.set(f"signal_{coin}", cached, ttl=900)
                return cached

            if current["status"] == "cooldown":
                if not state.is_available(coin):
                    return None

            candles = await _load_candles(coin)
            if not candles:
                return None

            result = await run_signal(
                coin    = coin,
                df_4h   = candles["4h"],
                df_1h   = candles["1h"],
                df_15m  = candles["15m"],
                balance = balance,
            )

            current = state.get(coin)

            if result.get("signal"):
                state.set_watching(coin, {
                    "direction": result["direction"],
                    "sweep":     result.get("sweep", {}),
                    "zone":      result.get("zone",  {}),
                })
                coin_status = "watching"

            elif result.get("zone_found") and result.get("sweep_found"):
                if current["status"] not in ("in_trade", "cooldown"):
                    state.set_watching(coin, {
                        "direction": result["direction"],
                        "sweep":     result.get("sweep", {}),
                        "zone":      result.get("zone",  {}),
                    })
                coin_status = "watching"

            elif result.get("sweep_found"):
                if current["status"] not in ("in_trade", "cooldown", "watching"):
                    state.set_watching(coin, {
                        "direction": result["direction"],
                        "sweep":     result.get("sweep", {}),
                        "zone":      {},
                    })
                coin_status = "watching"

            else:
                if current["status"] == "watching":
                    state.set_idle(coin)
                coin_status = "idle"

            ticker  = _get_ticker_from_redis(coin)
            funding = _get_funding_from_redis(coin)
            price   = get_mark_price(coin) or 0
            regime  = _derive_regime(result, coin_status)
            session = _derive_session()
            score   = _build_partial_score(result)

            sweep_data = result.get("sweep") or {}

            cache_entry = {
                "coin":      coin,
                "grade":     result.get("grade", "--") if result.get("signal") else (
                    "B" if score >= 50 else
                    "C" if score >= 30 else "--"
                ),
                "direction": result.get("direction", "--"),
                "score":     score,
                "state":     coin_status,
                "signal":    result if result.get("signal") else {},
                "market": {
                    "price":      price,
                    "change24":   ticker["change24"],
                    "change_pos": ticker["change_pos"],
                    "funding":    funding,
                },
                "sweep": {
                    "detected":  result.get("sweep_found", False),
                    "score":     result.get("sweep_score", 0),
                    "label":     sweep_data.get("level_label", "") if sweep_data else "",
                    "age_hours": sweep_data.get("age_hours",  0)   if sweep_data else 0,
                },
                "zone":      result.get("zone", {}),
                "narrative": result.get("narrative", ""),
                "regime":    regime,
                "session":   session,
                "explanation": {
                    "thesis":           result.get("narrative", ""),
                    "confidence_label": result.get("grade", "--") if result.get("signal") else "",
                },
                "actual_rr":  result.get("rr1", 0),
                "cached_at":  time.time(),
                "wconf": {
                    "norm_score":   score,
                    "market_score": score,
                    "entry_score":  round(result.get("trigger_score", 0) * 100) if result.get("trigger_score") else 0,
                    "btc_score":    0,
                    "factors":      [],
                },
            }

            cache.set(f"signal_{coin}", cache_entry, ttl=900)

            if not result.get("signal"):
                return cache_entry

            db_id = _save_signal(result)

            if db_id:
                result["db_id"] = db_id
                _write_redis(coin, result, db_id)

                if cfg.CONTENT_ENABLED and result.get("grade") in ("A+", "A"):
                    asyncio.create_task(_run_content(db_id))

                await send_signal(
                    result, coin,
                    result.get("grade", ""),
                    session,
                )

                await _execute_trade(coin, result, db_id)

            return cache_entry

        except Exception as e:
            log.error("_analyze_coin %s: %s", coin, e)
            return None


async def _run_content(db_id: int) -> None:
    try:
        from content.pipeline import run_content_pipeline
        await run_content_pipeline(db_id)
    except Exception as e:
        log.error("Content pipeline: %s", e)


async def _on_kline_closed(coin: str, kline: dict) -> None:
    try:
        current = state.get(coin)
        if current["status"] not in ("watching", "idle"):
            return

        import pandas as pd

        df_row = pd.DataFrame([{
            "timestamp": pd.Timestamp(kline["timestamp"], unit="ms"),
            "open":      kline["open"],
            "high":      kline["high"],
            "low":       kline["low"],
            "close":     kline["close"],
            "volume":    kline["volume"],
        }]).set_index("timestamp")

        save_candles(coin, kline["tf"], df_row)

        balance = await _get_balance()
        if balance <= 0:
            return

        await _analyze_coin(coin, balance)

    except Exception as e:
        log.error("_on_kline_closed %s: %s", coin, e)


async def scan_all_coins() -> list:
    async with _scan_lock:
        log.info("Scan started — %s coins", len(cfg.COINS))

        balance = await _get_balance()
        if balance <= 0:
            log.warning("Scan aborted — zero balance")
            return []

        state.tick_cooldowns()

        results = await asyncio.gather(
            *[_analyze_coin(c, balance) for c in cfg.COINS],
            return_exceptions=True
        )

        valid = [r for r in results if r and not isinstance(r, Exception)]
        valid.sort(key=lambda x: x.get("score", 0), reverse=True)

        _write_active_pairs()

        await send_scan_summary(valid)

        from events import emit
        asyncio.create_task(emit("scan_complete"))

        log.info("Scan complete — %s results", len(valid))
        return valid


def _write_active_pairs() -> None:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return
        pairs = [f"{c}/USDT:USDT" for c in cfg.COINS]
        r.setex("pairs:active", 1800, json.dumps({"pairs": pairs, "refresh_period": 1800}))
    except Exception as e:
        log.error("_write_active_pairs: %s", e)


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


def register_kline_handler() -> None:
    on_kline_closed(_on_kline_closed)