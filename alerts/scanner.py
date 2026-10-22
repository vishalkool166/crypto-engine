import asyncio
import json
import logging
import time
from data.fetcher import fetch_and_store, get_funding_rate
from data.cache import cache
from data.rejection_stats import record_scan, get_total_stats, get_top_rejections
from database import get_session, Signal as SignalModel, PortfolioSnapshot
from trade.exchange import get_balance
from trade.ws import get_mark_price, on_kline_closed
from config import cfg, get_coin_config, CIRCUIT_BREAKER_CONFIG
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

_daily_sl_count:    int   = 0
_daily_sl_date:     str   = ""


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


def _check_coin_circuit_breaker(coin: str, df_4h) -> bool:
    """Use actual CLOSED four-hour candles, never Redis's 24h ticker change.

    Stale, incomplete or invalid candles cannot authorize a new exposure.
    The caller fetches fresh data before invoking this check.
    """
    try:
        import math
        import pandas as pd
        if df_4h is None or len(df_4h) < 2:
            return False
        previous = float(df_4h["close"].iloc[-2])
        current = float(df_4h["close"].iloc[-1])
        if not all(math.isfinite(v) and v > 0 for v in (previous, current)):
            return False
        last_open = pd.Timestamp(df_4h.index[-1])
        prior_open = pd.Timestamp(df_4h.index[-2])
        if last_open.tzinfo is None:
            last_open = last_open.tz_localize("UTC")
            prior_open = prior_open.tz_localize("UTC")
        else:
            last_open = last_open.tz_convert("UTC")
            prior_open = prior_open.tz_convert("UTC")
        if last_open - prior_open != pd.Timedelta(hours=4):
            return False
        age = pd.Timestamp.now(tz="UTC") - (last_open + pd.Timedelta(hours=4))
        # Last bar must be CLOSED and no older than one regular four-hour cycle.
        if age < pd.Timedelta(0) or age > pd.Timedelta(hours=4, minutes=10):
            return False
        change_4h = (current / previous - 1.0) * 100.0
        if abs(change_4h) > CIRCUIT_BREAKER_CONFIG["coin_drop_4h_pct"]:
            log.warning("4h circuit breaker: %s moved %.2f%%; blocking entry", coin, change_4h)
            return False
        return True
    except Exception as e:
        log.warning("4h circuit breaker unavailable for %s: %s", coin, e)
        return False


def record_sl_hit(coin: str) -> None:
    global _daily_sl_count, _daily_sl_date
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    if _daily_sl_date != today:
        _daily_sl_count = 0
        _daily_sl_date  = today
    _daily_sl_count += 1

    if _daily_sl_count >= CIRCUIT_BREAKER_CONFIG['daily_sl_pause_count']:
        log.warning(
            "Circuit breaker: %s SL hits today — pausing new entries",
            _daily_sl_count
        )
        _save_portfolio_snapshot(circuit_level=3)


def _get_portfolio_circuit_level() -> int:
    try:
        from database import SessionLocal, PortfolioSnapshot
        db = SessionLocal()
        try:
            latest = db.query(PortfolioSnapshot).order_by(
                PortfolioSnapshot.snapshot_at.desc()
            ).first()
            return latest.circuit_level if latest else 0
        finally:
            db.close()
    except Exception as e:
        log.error("Circuit snapshot unavailable: %s; halting new entries", e)
        return 4


def _resolve_circuit_level(current: int, requested: int | None) -> int:
    """Periodic snapshots cannot erase an earlier halt without operator action."""
    if requested is None:
        return current
    return max(current, requested)


def _save_portfolio_snapshot(circuit_level: int | None = None, notes: str = "", *, equity: float | None = None) -> None:
    """Record verified futures account equity, never static configured capital.

    Routine scans require a freshly fetched account balance. When an event only
    asks to raise the risk circuit without fresh equity, retain the last value
    but HALT further entries (level 4) until a fresh snapshot is obtained.
    """
    try:
        import math
        from datetime import datetime, timezone, timedelta
        from database import SessionLocal, PortfolioSnapshot, Trade as TradeModel
        with SessionLocal() as db:
            latest = db.query(PortfolioSnapshot).order_by(PortfolioSnapshot.id.desc()).first()
            valid = (equity is not None and math.isfinite(equity) and equity > 0)
            if not valid and latest is None:
                log.error("Portfolio snapshot unavailable: no verified equity; refusing placeholder")
                return
            total_value = float(equity if valid else latest.total_value)
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
            recent = db.query(PortfolioSnapshot).filter(PortfolioSnapshot.snapshot_at >= cutoff).order_by(PortfolioSnapshot.id.desc()).limit(2000).all()
            peak_30d = max([total_value] + [float(s.total_value) for s in recent if s.total_value > 0])
            dd_pct = round((total_value/peak_30d - 1)*100, 2)
            requested = int(circuit_level or 0)
            # Missing equity must never clear a previous circuit or authorize entries.
            if not valid:
                requested = max(requested, 4)
                notes = (notes + " stale_equity_halt").strip()
            if dd_pct <= -CIRCUIT_BREAKER_CONFIG["portfolio_dd_level4_pct"]:
                requested = max(requested, 4)
            elif dd_pct <= -CIRCUIT_BREAKER_CONFIG["portfolio_dd_level3_pct"]:
                requested = max(requested, 3)
            elif dd_pct <= -CIRCUIT_BREAKER_CONFIG["portfolio_dd_level2_pct"]:
                requested = max(requested, 2)
            elif dd_pct <= -CIRCUIT_BREAKER_CONFIG["portfolio_dd_level1_pct"]:
                requested = max(requested, 1)
            current_level = int(latest.circuit_level or 0) if latest else 0
            active = db.query(TradeModel).filter(TradeModel.is_active.is_(True)).count()
            db.add(PortfolioSnapshot(total_value=total_value,peak_30d=peak_30d,drawdown_pct=dd_pct,open_positions=active,circuit_level=max(current_level,requested),notes=notes))
            db.commit()
    except Exception as exc:
        log.error("_save_portfolio_snapshot failed closed: %s", type(exc).__name__)


async def _refresh_portfolio_equity() -> bool:
    """Read fresh same-mode Binance futures balance for drawdown governor."""
    try:
        import math
        from trade.exchange import get_account_equity
        equity = await get_account_equity()
        if not math.isfinite(equity) or equity <= 0:
            raise ValueError("Exchange equity not positive")
        _save_portfolio_snapshot(equity=equity,notes="exchange_futures_equity")
        return True
    except Exception as exc:
        log.error("Current Binance equity unavailable; blocking entries: %s",type(exc).__name__)
        _save_portfolio_snapshot(circuit_level=4,notes="exchange_equity_unavailable")
        return False


def _get_daily_sl_count() -> int | None:
    """Count confirmed SL closures from durable trade rows, not process memory.

    Worker restart must not reset the daily stop-loss circuit breaker.
    """
    try:
        from datetime import datetime, timezone
        from database import SessionLocal, Trade as TradeModel
        now = datetime.now(timezone.utc)
        start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        with SessionLocal() as db:
            return db.query(TradeModel).filter(
                TradeModel.closed_at >= start,
                TradeModel.close_reason == "sl_hit",
                TradeModel.execution_mode == cfg.TRADING_MODE,
            ).count()
    except Exception as error:
        log.error("Daily stop-loss count unavailable: %s", error)
        return None


def _verified_equity_is_fresh() -> bool:
    """Risk gate independent of the legacy size-multiplier calculation."""
    try:
        from datetime import datetime, timezone, timedelta
        with __import__("database", fromlist=["SessionLocal"]).SessionLocal() as db:
            latest = db.query(PortfolioSnapshot).order_by(PortfolioSnapshot.id.desc()).first()
            if latest is None or latest.snapshot_at is None or "exchange_futures_equity" not in (latest.notes or ""):
                return False
            stamp = latest.snapshot_at.replace(tzinfo=timezone.utc) if latest.snapshot_at.tzinfo is None else latest.snapshot_at
            return latest.total_value > 0 and timedelta(0) <= datetime.now(timezone.utc) - stamp < timedelta(minutes=5)
    except Exception:
        return False


def _get_portfolio_size_multiplier() -> float:
    level = _get_portfolio_circuit_level()
    daily_stop_count = _get_daily_sl_count()
    if daily_stop_count is None or daily_stop_count >= CIRCUIT_BREAKER_CONFIG['daily_sl_pause_count']:
        return 0.0
    mult_map = {
        0: 1.0,
        1: CIRCUIT_BREAKER_CONFIG['size_mult_level1'],
        2: CIRCUIT_BREAKER_CONFIG['size_mult_level2'],
        3: CIRCUIT_BREAKER_CONFIG['size_mult_level3'],
        4: CIRCUIT_BREAKER_CONFIG['size_mult_level4'],
        5: CIRCUIT_BREAKER_CONFIG['size_mult_level5'],
    }
    return mult_map.get(level, 0.0)


def _meets_coin_rr(coin: str, actual_rr: float) -> bool:
    """Use the configured TP requirement rather than a blanket 2R gate.

    BNB and LTC are deliberately configured at 1.5R and were previously
    rejected by a downstream hard-coded 2R filter.
    """
    import math
    threshold = float(get_coin_config(coin).get("tp", 2.0))
    return (math.isfinite(actual_rr) and math.isfinite(threshold) and
            threshold > 0 and actual_rr + 1e-6 >= 0.90 * threshold)


def _save_signal(signal: dict) -> int | None:
    if signal.get("grade") not in cfg.MIN_GRADE_TO_TRADE:
        return None
    if signal.get("direction") not in ("LONG", "SHORT"):
        return None
    if not signal.get("entry"):
        return None
    if not _meets_coin_rr(signal["coin"], float(signal.get("rr1") or 0)):
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
                factor_scores  = json.dumps(signal.get("trace", {}), default=str),
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

            # The 1h websocket path can call _analyze_coin outside the scheduler.
            # Neither path may rely on stale or unverifiable equity.
            if not _verified_equity_is_fresh():
                log.warning("_analyze_coin: fresh Binance equity required for %s",coin)
                return None
            portfolio_mult = _get_portfolio_size_multiplier()
            if portfolio_mult == 0.0:
                log.info("_analyze_coin: portfolio circuit breaker active — skipping %s", coin)
                return None

            df_4h = await fetch_and_store(coin, "4h", limit=300)
            df_1h = await fetch_and_store(coin, "1h", limit=300)

            if df_4h is None or len(df_4h) < 200:
                return None
            if df_1h is None or len(df_1h) < 50:
                return None
            if not _check_coin_circuit_breaker(coin, df_4h):
                log.warning("_analyze_coin: invalid, stale or volatile 4h data for %s", coin)
                return None

            # Shadow research never changes the existing production decisions.
            try:
                from strategies.registry import scan as scan_candidates
                from research.ledger import record_shadow
                await asyncio.to_thread(record_shadow, coin, scan_candidates(df_4h))
            except Exception as shadow_exc:
                log.warning("Shadow research unavailable for %s: %s", coin, shadow_exc)

            from agents.signal_agent import run as agent_run
            result = await agent_run(
                coin    = coin,
                df_4h   = df_4h,
                df_1h   = df_1h,
                balance = balance,
            )

            from engines.decision_trace import DecisionTrace, store_trace
            recorded = DecisionTrace(coin=coin, direction=result.get("direction","NEUTRAL"),
                steps=result.get("trace",{}).get("steps",[]),
                final_decision="TRADE" if result.get("signal") else "NO_TRADE",
                final_score=result.get("score",0),final_grade=result.get("grade","F"),
                stopped_at=result.get("reason"),regime=result.get("regime",""),session=result.get("session",""))
            store_trace(recorded)

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
                "adx"   :    result.get("adx", 0),
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
        if not await _refresh_portfolio_equity():
            return []
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
        # Fresh equity was recorded before the scan; do not rewrite it with a constant.

        await send_scan_summary(valid)

        from events import emit
        asyncio.create_task(emit("scan_complete"))

        log.info("Scan complete — %s results in %sms", len(valid), scan_ms)
        return valid


async def scan_single_coin(coin: str) -> dict | None:
    try:
        if not await _refresh_portfolio_equity():
            return None
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
            "circuit_level":   _get_portfolio_circuit_level(),
            "daily_sl_count":  _daily_sl_count,
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
        if not await _refresh_portfolio_equity():
            return
        balance = await _get_cached_balance()
        if balance <= 0:
            return
        await _analyze_coin(coin, balance)
    except Exception as e:
        log.error("_on_kline_closed %s: %s", coin, e)