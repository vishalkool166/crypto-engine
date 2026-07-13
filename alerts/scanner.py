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

_cached_balance:    float = 0.0
_balance_cached_at: float = 0.0
_BALANCE_CACHE_TTL: float = 60.0

_cached_1d: dict = {}
_cached_1w: dict = {}
_HTF_CACHE_TTL   = 3600.0
_htf_cached_at:  float = 0.0


def _get_ticker_from_redis(coin: str) -> dict:
    try:
        from redis_client import get_redis
        import json
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
    relevance = sweep.get("relevance", {}).get("label", "") if sweep else ""

    if coin_status == "in_trade":
        return f"{'Bullish' if direction == 'LONG' else 'Bearish'} — In Trade"
    if result.get("signal"):
        return (
            f"{'Bullish' if direction == 'LONG' else 'Bearish'} — {relevance} Sweep"
            if relevance
            else f"{'Bullish' if direction == 'LONG' else 'Bearish'} — Signal"
        )
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
    sweep_score   = result.get("sweep_score",   0) or 0
    zone_score    = result.get("zone_score",    0) or 0
    trigger_score = result.get("trigger_score", 0) or 0

    if result.get("signal"):
        return round((result.get("score", 0) or 0) * 100)
    if result.get("zone_found") and result.get("sweep_found"):
        return round((sweep_score * 0.40 + zone_score * 0.35) * 100)
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


async def _load_htf_candles() -> dict:
    global _cached_1d, _cached_1w, _htf_cached_at

    now = time.time()
    if _cached_1d and (now - _htf_cached_at) < _HTF_CACHE_TTL:
        return {"1d": _cached_1d, "1w": _cached_1w}

    log.info("Loading higher timeframe candles for all coins")
    new_1d = {}
    new_1w = {}

    for coin in cfg.COINS:
        try:
            df_1d = await fetch_and_store(coin, "1d", limit=200)
            new_1d[coin] = df_1d
        except Exception as e:
            log.warning("HTF 1D load failed %s: %s", coin, e)
            new_1d[coin] = None

        try:
            df_1w = await fetch_and_store(coin, "1w", limit=100)
            new_1w[coin] = df_1w
        except Exception as e:
            log.warning("HTF 1W load failed %s: %s", coin, e)
            new_1w[coin] = None

        await asyncio.sleep(0.2)

    _cached_1d      = new_1d
    _cached_1w      = new_1w
    _htf_cached_at  = now
    log.info("Higher timeframe candles loaded for %s coins", len(cfg.COINS))
    return {"1d": new_1d, "1w": new_1w}


async def _get_balance() -> float:
    try:
        b = await get_balance()
        return float(b.get("free", 0))
    except Exception as e:
        log.error("_get_balance: %s", e)
        return 0.0


async def _get_cached_balance() -> float:
    global _cached_balance, _balance_cached_at
    if _cached_balance > 0 and (time.time() - _balance_cached_at) < _BALANCE_CACHE_TTL:
        return _cached_balance
    balance = await _get_balance()
    if balance > 0:
        _cached_balance    = balance
        _balance_cached_at = time.time()
    return balance


def _build_factor_scores(result: dict) -> dict:
    zone = result.get("zone") or {}
    return {
        "liquidity_sweep":     round(result.get("sweep_score",   0) * 12, 2),
        "displacement":        round(result.get("trigger_score", 0) * 11, 2),
        "retest_confirmation": round(result.get("zone_score",    0) * 12, 2),
        "order_blocks":        round(zone.get("score", 0) * 4,            2) if zone.get("type") == "OB" else 0,
        "market_structure":    round(result.get("sweep_score",   0) * 9,  2),
        "volume_expansion":    round(result.get("trigger_score", 0) * 7,  2),
        "market_regime":       8 if result.get("direction") in ("LONG", "SHORT") else 0,
        "session_timing":      6 if _derive_session() in ("London", "London/NY Overlap", "New York") else 2,
        "btc_alignment":       6,
        "oi_behavior":         4,
        "funding_extreme":     0,
        "rsi_divergence":      0,
        "atr_volatility":      2,
        "rsi_context":         1,
        "macd_histogram":      1,
        "weekly_filter":       8,
    }


def _save_signal(signal: dict) -> int | None:
    if signal.get("grade") not in cfg.MIN_GRADE_TO_TRADE:
        return None
    if signal.get("direction") not in ("LONG", "SHORT"):
        return None
    if not signal.get("entry"):
        return None

    try:
        factor_scores = _build_factor_scores(signal)

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

            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)

            row = SignalModel(
                coin              = signal["coin"],
                direction         = signal["direction"],
                grade             = signal["grade"],
                score             = signal["score"],
                signal_type       = signal["signal_type"],
                entry             = signal["entry"],
                sl                = signal["sl"],
                tp1               = signal["tp1"],
                tp2               = signal.get("tp2"),
                sl_pct            = signal["sl_pct"],
                risk_amt          = signal["risk_amt"],
                risk_pct          = signal["risk_pct"],
                position          = signal["pos_size"],
                leverage          = str(signal["leverage"]) + "x",
                sweep_score       = signal["sweep_score"],
                retest_score      = 0,
                disp_score        = signal["trigger_score"],
                funding           = 0,
                oi_signal         = "",
                outcome           = "pending",
                atr_at_entry      = signal.get("atr_4h"),
                factor_scores     = json.dumps(factor_scores),
                market_score      = round(signal.get("sweep_score",   0) * 100, 2),
                entry_score       = round(signal.get("trigger_score", 0) * 100, 2),
                btc_score         = 6.0,
                day_of_week       = now.weekday(),
                hour_of_day       = now.hour,
                system_version    = cfg.SYSTEM_VERSION,
            )
            db.add(row)
            db.flush()
            db.refresh(row)
            log.info(
                "Signal saved ID:%s %s %s grade:%s alignment:%s",
                row.id, signal["coin"], signal["direction"],
                signal["grade"], signal.get("alignment_str", "none")
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


async def _capture_signal_snapshot(
    signal_id: int,
    signal:    dict,
    candles:   dict,
    balance:   float,
    sizing:    dict,
) -> None:
    try:
        from ml.observer import capture
        from engines.indicators import calculate_all

        d4h  = calculate_all(candles["4h"].iloc[-200:],  timeframe="4h")
        d1h  = calculate_all(candles["1h"].iloc[-300:],  timeframe="1h")
        d15m = calculate_all(candles["15m"].iloc[-200:], timeframe="15m")

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: capture(
                signal_id     = signal_id,
                signal        = signal,
                d4h           = d4h,
                d1h           = d1h,
                d15m          = d15m,
                balance       = balance,
                sizing_result = sizing,
            )
        )
    except Exception as e:
        log.error("_capture_signal_snapshot signal_id=%s: %s", signal_id, e)


async def _execute_trade(coin: str, signal: dict, db_id: int) -> None:
    try:
        from trade.executor import open_position, has_open_trade_or_position

        if await has_open_trade_or_position(coin):
            log.info("_execute_trade: %s already has position", coin)
            return

        from datetime import datetime, timezone
        _hour = datetime.now(timezone.utc).hour
        if 8   <= _hour < 13: _session = "London"
        elif 13 <= _hour < 17: _session = "London/NY Overlap"
        elif 17 <= _hour < 21: _session = "New York"
        elif 0  <= _hour < 8:  _session = "Asia"
        else:                   _session = "Off Hours"

        _regime = signal.get("regime", "")
        if not _regime:
            _regime = _derive_regime(signal, "watching")

        sizing_result = {
            "risk_pct":      signal.get("risk_pct",      0),
            "risk_amt":      signal.get("risk_amt",      0),
            "position_size": signal.get("pos_size",      0),
            "stake":         signal.get("stake",         0),
            "leverage":      signal.get("leverage",      0),
            "drawdown_pct":  signal.get("drawdown_pct",  0),
            "win_rate":      signal.get("win_rate"),
            "streak":        signal.get("streak",        0),
            "streak_type":   signal.get("streak_type"),
            "today_pnl":     signal.get("today_pnl",     0),
            "open_trades":   signal.get("open_trades",   0),
            "sweep_score":   signal.get("sweep_score",   0),
            "zone_score":    signal.get("zone_score",    0),
            "trigger_score": signal.get("trigger_score", 0),
        }

        result = await open_position(
            coin          = coin,
            direction     = signal["direction"],
            entry         = float(signal["entry"]),
            sl            = float(signal["sl"]),
            tp            = float(signal["tp1"]),
            stake         = float(signal["stake"]),
            leverage      = int(signal["leverage"]),
            signal_id     = db_id,
            grade         = signal["grade"],
            regime        = _regime,
            session       = _session,
            score         = float(signal["score"]),
            tp2           = float(signal["tp2"]) if signal.get("tp2") else None,
            atr_15m       = float(signal.get("atr_15m", 0)),
            sizing_result = sizing_result,
        )

        if result.get("success"):
            current_state = state.get(coin)
            state.set_in_trade(coin, result["trade_id"], current_state.get("setup", {}))
            log.info(
                "Trade opened: %s %s grade:%s trade_id:%s alignment:%s",
                coin, signal["direction"], signal["grade"],
                result["trade_id"], signal.get("alignment_str", "none")
            )
        else:
            log.error("Trade open failed %s: %s", coin, result.get("error"))

    except Exception as e:
        log.error("_execute_trade %s: %s", coin, e, exc_info=True)


async def _analyze_coin(
    coin:    str,
    balance: float,
    htf:     dict,
) -> dict | None:
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
                    cache.set(f"signal_{coin}", cached, ttl=1800)
                return cached

            if current["status"] == "cooldown":
                if not state.is_available(coin):
                    return None

            candles = await _load_candles(coin)
            if not candles:
                return None

            df_1d = htf.get("1d", {}).get(coin)
            df_1w = htf.get("1w", {}).get(coin)

            result = await run_signal(
                coin    = coin,
                df_4h   = candles["4h"],
                df_1h   = candles["1h"],
                df_15m  = candles["15m"],
                balance = balance,
                df_1d   = df_1d,
                df_1w   = df_1w,
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
            zone_data  = result.get("zone")  or {}
            alignment  = result.get("alignment") or {}

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
                "zone": {
                    "type":         zone_data.get("type",         "—"),
                    "top":          zone_data.get("top",           0),
                    "bottom":       zone_data.get("bottom",        0),
                    "mid":          zone_data.get("mid",           0),
                    "distance_pct": zone_data.get("distance_pct", None),
                    "touch_count":  zone_data.get("touch_count",  0),
                    "score":        zone_data.get("score",         0),
                    "origin_desc":  zone_data.get("origin_desc",  ""),
                },
                "alignment": {
                    "daily":     alignment.get("daily",     "NEUTRAL"),
                    "weekly":    alignment.get("weekly",    "NEUTRAL"),
                    "alignment": alignment.get("alignment", "none"),
                    "size_mult": alignment.get("size_mult", 1.0),
                },
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
                    "market_score": round(result.get("sweep_score",   0) * 100) if result.get("sweep_score")   else 0,
                    "entry_score":  round(result.get("trigger_score", 0) * 100) if result.get("trigger_score") else 0,
                    "btc_score":    0,
                    "factors":      [],
                },
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

                sizing_result = {
                    "risk_pct":      result.get("risk_pct",  0),
                    "risk_amt":      result.get("risk_amt",  0),
                    "position_size": result.get("pos_size",  0),
                    "stake":         result.get("stake",     0),
                    "leverage":      result.get("leverage",  0),
                }

                asyncio.create_task(_capture_signal_snapshot(
                    signal_id = db_id,
                    signal    = result,
                    candles   = candles,
                    balance   = balance,
                    sizing    = sizing_result,
                ))

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

        balance = await _get_cached_balance()
        if balance <= 0:
            return

        htf = {"1d": _cached_1d, "1w": _cached_1w}
        await _analyze_coin(coin, balance, htf)

    except Exception as e:
        log.error("_on_kline_closed %s: %s", coin, e)


async def scan_all_coins() -> list:
    async with _scan_lock:
        log.info("Scan started — %s coins", len(cfg.COINS))

        balance = await _get_cached_balance()
        if balance <= 0:
            log.warning("Scan aborted — zero balance")
            return []

        state.tick_cooldowns()

        htf = await _load_htf_candles()

        results = await asyncio.gather(
            *[_analyze_coin(c, balance, htf) for c in cfg.COINS],
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
        r.setex("pairs:active", 1800, json.dumps({
            "pairs":          pairs,
            "refresh_period": 1800,
        }))
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