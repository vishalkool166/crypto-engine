import asyncio
import json
import logging
import time
from data.fetcher import fetch_and_store, get_funding_rate
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


def _write_cache(coin: str, result: dict) -> None:
    ttl = 900
    cache.set(f"signal_{coin}", result, ttl=ttl)


async def _execute_trade(coin: str, signal: dict, db_id: int) -> None:
    try:
        from trade.executor import open_position, has_open_trade_or_position
        from engines.state import set_in_trade, get as get_state

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
        )

        if result.get("success"):
            current_state = get_state(coin)
            set_in_trade(coin, result["trade_id"], current_state.get("setup", {}))
            log.info("Trade opened: %s %s grade:%s trade_id:%s",
                     coin, signal["direction"], signal["grade"], result["trade_id"])
        else:
            log.error("Trade open failed %s: %s", coin, result.get("error"))

    except Exception as e:
        log.error("_execute_trade %s: %s", coin, e, exc_info=True)


async def _analyze_coin(coin: str, balance: float) -> dict | None:
    async with _scan_semaphore:
        try:
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

            price   = get_mark_price(coin) or float(candles["4h"]["close"].iloc[-1])
            funding = await get_funding_rate(coin)

            cache_entry = {
                "coin":      coin,
                "grade":     result.get("grade",     "--"),
                "direction": result.get("direction", "--"),
                "score":     result.get("score",     0),
                "state":     state.get(coin)["status"],
                "signal":    result if result.get("signal") else {},
                "market": {
                    "price":      price,
                    "change24":   0,
                    "funding":    funding,
                    "change_pos": True,
                },
                "sweep":     result.get("sweep",   {}),
                "zone":      result.get("zone",    {}),
                "narrative": result.get("narrative", ""),
                "explanation": {
                    "thesis":           result.get("narrative", ""),
                    "confidence_label": result.get("grade", "--"),
                },
                "actual_rr":  result.get("rr1", 0),
                "cached_at":  time.time(),
                "wconf": {
                    "norm_score":   round(result.get("score", 0) * 100),
                    "market_score": round(result.get("score", 0) * 100),
                    "entry_score":  round(result.get("trigger_score", 0) * 100),
                    "btc_score":    0,
                    "factors":      [],
                },
            }

            _write_cache(coin, cache_entry)

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
                    "",
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
        if not state.is_watching(coin):
            return

        from data.store import save_candles
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
                gw = [s for s in gt if s.outcome == "win"]
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