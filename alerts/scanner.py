import asyncio
import logging
import time
import json
from config import cfg
from data.cache import cache
from data.store import load_candles
from data.fetcher import get_15m_data
from engines.validator import validate_all_timeframes
from engines.indicators import calculate_all
from engines.sweep import detect_sweep
from engines.displacement import detect_displacement
from engines.bias import get_htf_bias
from engines.zone_finder import get_active_zone
from engines.trigger import check_15m_trigger
from engines.signal_core import build_signal, validate_risk
from engines.coin_state import state_manager
from engines.session import get_session
from database import get_session as get_db_session, Signal as SignalModel
from alerts.telegram import send_signal, send_scan_summary

log = logging.getLogger(__name__)


def _extract_key_levels(df_1d, df_1w) -> dict:
    return {
        "pdh": float(df_1d.iloc[-2]["high"])  if len(df_1d) >= 2 else 0,
        "pdl": float(df_1d.iloc[-2]["low"])   if len(df_1d) >= 2 else 0,
        "pdc": float(df_1d.iloc[-2]["close"]) if len(df_1d) >= 2 else 0,
        "pwh": float(df_1w.iloc[-2]["high"])  if len(df_1w) >= 2 else 0,
        "pwl": float(df_1w.iloc[-2]["low"])   if len(df_1w) >= 2 else 0,
    }


def _write_signal_to_redis(coin: str, signal: dict, db_id: int):
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return
        r.setex(f"signal:{coin}USDT", 1800, json.dumps({
            "coin":        coin,
            "grade":       signal.get("grade"),
            "direction":   signal.get("direction"),
            "entry":       signal.get("entry"),
            "sl":          signal.get("sl"),
            "stoploss":    signal.get("sl"),
            "tp1":         signal.get("tp1"),
            "tp":          signal.get("tp1"),
            "score":       signal.get("score", 0),
            "signal_id":   db_id,
            "valid_until": time.time() + 1800,
        }))
        log.info("Signal written to Redis: %s %s %s", coin, signal.get("grade"), signal.get("direction"))
    except Exception as e:
        log.error("Redis signal write error %s: %s", coin, e)


def _write_coin_cache(
    coin:      str,
    machine_state: str,
    context:   dict,
    signal:    dict | None = None,
    price:     float       = 0,
    ttl:       int         = 900,
):
    try:
        zone      = context.get("zone", {})
        bias      = context.get("bias", {})
        direction = context.get("direction", "--")

        entry = {
            "coin":      coin,
            "grade":     signal.get("grade",     "--") if signal else "--",
            "direction": signal.get("direction", direction) if signal else direction,
            "score":     signal.get("score",     0)   if signal else 0,
            "state":     machine_state,
            "signal":    signal or {},
            "market": {
                "price":    price,
                "change24": 0,
                "funding":  0,
            },
            "regime":    bias.get("strength", "--") if bias else "--",
            "session":   get_session().get("name", "--"),
            "sweep": {
                "detected":   bias.get("sweep_detected", False) if bias else False,
                "confirmed":  bias.get("sweep_detected", False) if bias else False,
                "score":      bias.get("sweep_score",    0)     if bias else 0,
                "label":      bias.get("sweep_label",    "")    if bias else "",
                "age_hours":  bias.get("sweep_age_hours", 0)    if bias else 0,
            },
            "displacement": {
                "confirmed": bias.get("displacement",        False) if bias else False,
                "strong":    bias.get("displacement_strong", False) if bias else False,
                "range_mult":bias.get("displacement_atr",    0)     if bias else 0,
            },
            "retest": {
                "confirmed": machine_state == "signal_ready",
                "zone_type": zone.get("type", "") if zone else "",
                "score":     0,
            },
            "zone":      zone or {},
            "bias":      bias or {},
            "d1d":       context.get("d1d", {}),
            "d4h":       context.get("d4h", {}),
            "oi_matrix": {},
            "explanation": {
                "thesis":           signal.get("narrative", "") if signal else "",
                "confidence_label": signal.get("grade",     "") if signal else "",
            },
            "actual_rr":      signal.get("actual_rr", 0) if signal else 0,
            "ml_probability": None,
            "cached_at":      time.time(),
        }

        cache.set(f"signal_{coin}", entry, ttl=ttl)
    except Exception as e:
        log.error("_write_coin_cache error %s: %s", coin, e)


def _write_active_pairs_to_redis():
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return
        pairs = [f"{coin}/USDT:USDT" for coin in cfg.COINS]
        r.setex("pairs:active", 1800, json.dumps({"pairs": pairs, "refresh_period": 1800}))
    except Exception as e:
        log.error("Redis active pairs write failed: %s", e)


def save_signal_to_db(signal: dict, coin: str, session: dict) -> int | None:
    if signal.get("grade") not in cfg.MIN_GRADE_TO_TRADE:
        return None
    if signal.get("direction") not in ("LONG", "SHORT"):
        return None
    if not signal.get("entry"):
        return None

    try:
        with get_db_session() as db:
            existing = db.query(SignalModel).filter(
                SignalModel.coin      == coin,
                SignalModel.direction == signal["direction"],
                SignalModel.outcome   == "pending",
            ).first()

            if existing:
                from trade.executor import has_open_trade
                if has_open_trade(coin):
                    return None
                existing.outcome = "expired"

            row = SignalModel(
                coin         = coin,
                direction    = signal["direction"],
                grade        = signal["grade"],
                score        = signal["score"],
                signal_type  = signal["signal_type"],
                entry        = signal.get("entry", 0),
                sl           = signal.get("sl", 0),
                tp1          = signal.get("tp1", 0),
                tp2          = signal.get("tp2"),
                sl_pct       = signal.get("sl_pct", 0),
                risk_amt     = signal.get("risk_amt", 0),
                risk_pct     = signal.get("risk_pct", 0),
                position     = signal.get("pos_size", 0),
                leverage     = str(signal.get("leverage", 10)) + "x",
                regime       = signal.get("bias_strength", ""),
                session      = session.get("name", ""),
                sweep_score  = signal.get("sweep_score", 0),
                retest_score = 0,
                disp_score   = signal.get("displacement_atr", 0),
                funding      = 0,
                oi_signal    = "",
                outcome      = "pending",
                atr_at_entry = signal.get("atr_4h"),
            )
            db.add(row)
            db.flush()
            db.refresh(row)
            log.info("Signal saved ID:%s %s %s", row.id, coin, signal["grade"])
            return row.id
    except Exception as e:
        log.error("DB save error: %s", e)
        return None


async def _open_trade(coin: str, signal: dict, db_id: int):
    try:
        from trade.executor import has_open_trade_or_position, open_position
        from engines.capital import compute_allocation

        if await has_open_trade_or_position(coin):
            log.info("%s already has open position — skipping", coin)
            return

        allocation = await compute_allocation(
            signal      = signal,
            wconf       = {},
            regime      = {"type": signal.get("bias_strength", "moderate")},
            vol_profile = {
                "volatility_class": "normal",
                "atr_pct":          signal.get("atr_4h", 0) / signal.get("entry", 1) * 100,
                "adx":              20,
            },
            direction = signal.get("direction"),
        )

        if allocation.get("skip"):
            log.info("%s allocation skipped: %s", coin, allocation.get("reason"))
            return

        signal.update({
            "risk_amt": allocation["risk_amt"],
            "pos_size": allocation["pos_size"],
            "leverage": allocation["leverage"],
            "stake":    allocation["stake"],
        })

        result = await open_position(
            coin      = coin,
            direction = signal["direction"],
            entry     = float(signal["entry"]),
            sl        = float(signal["sl"]),
            tp        = float(signal["tp1"]),
            stake     = float(allocation["stake"]),
            leverage  = int(allocation["leverage"]),
            signal_id = db_id,
            grade     = signal["grade"],
            regime    = signal.get("bias_strength", ""),
            session   = signal.get("session_name", ""),
            score     = float(signal.get("score", 0)),
        )

        if result.get("success"):
            machine = state_manager.get(coin)
            machine.trade_opened()
            state_manager._persist(coin)
            log.info("Trade opened %s %s grade:%s", coin, signal["direction"], signal["grade"])
        else:
            log.error("Trade open failed %s: %s", coin, result.get("error"))

    except Exception as e:
        log.error("_open_trade error %s: %s", coin, e)


async def run_daily_bias_update():
    log.info("Daily bias update — %s coins", len(cfg.COINS))

    for coin in cfg.COINS:
        try:
            machine = state_manager.get(coin)

            if machine.state in ("trade_active", "cooldown"):
                continue

            df_1d = load_candles(coin, "1d", limit=500)
            df_1w = load_candles(coin, "1w", limit=200)
            df_4h = load_candles(coin, "4h", limit=500)

            if df_1d is None or df_1w is None or df_4h is None:
                log.warning("%s missing candle data — skipping", coin)
                continue

            validation = validate_all_timeframes(
                {"1d": df_1d, "1w": df_1w, "4h": df_4h}, coin
            )
            if not validation["valid"]:
                log.warning("%s data validation failed — skipping", coin)
                continue

            klines = validation["klines"]
            d1d    = calculate_all(klines["1d"], timeframe="1d")
            d1w    = calculate_all(klines["1w"], timeframe="1w")
            d4h    = calculate_all(klines["4h"], timeframe="4h")

            key_levels = _extract_key_levels(klines["1d"], klines["1w"])

            bias = get_htf_bias(d1w, d1d, klines["1d"], key_levels)

            price = d1d.get("price", 0)

            if not bias["valid"]:
                if machine.state != "no_bias":
                    machine.bias_lost()
                    state_manager._persist(coin)
                _write_coin_cache(
                    coin          = coin,
                    machine_state = "no_bias",
                    context       = {},
                    price         = price,
                    ttl           = 900,
                )
                log.debug("%s no bias: %s", coin, bias["no_bias_reason"])
                continue

            context_update = {
                "direction":           bias["direction"],
                "slope_defined":       bias["slope_defined"],
                "sweep_detected":      bias["sweep_detected"],
                "sweep_age_hours":     bias["sweep_age_hours"],
                "sweep_label":         bias["sweep_label"],
                "sweep_level":         bias["sweep_level"],
                "sweep_score":         bias["sweep_score"],
                "sweep_low":           bias["sweep_low"],
                "sweep_high":          bias["sweep_high"],
                "displacement":        bias["displacement"],
                "displacement_strong": bias["displacement_strong"],
                "displacement_atr":    bias["displacement_atr"],
                "strength":            bias["strength"],
                "atr":                 bias["atr"],
                "bias":                bias,
                "d1d":                 d1d,
                "d4h":                 d4h,
                "bias_updated_at":     time.time(),
            }

            state_manager.update_context(coin, context_update)

            if machine.state == "no_bias":
                machine.bias_detected()
                state_manager._persist(coin)

            _write_coin_cache(
                coin          = coin,
                machine_state = machine.state,
                context       = machine.context,
                price         = price,
                ttl           = 900,
            )

        except Exception as e:
            log.error("Daily bias update failed %s: %s", coin, e)

    log.info("Daily bias update complete")


async def run_zone_update():
    log.info("Zone update started")

    for coin in cfg.COINS:
        try:
            machine = state_manager.get(coin)

            if machine.state not in ("bias_defined", "zone_active"):
                continue

            df_4h = load_candles(coin, "4h", limit=500)
            df_1h = load_candles(coin, "1h", limit=300)

            if df_4h is None:
                continue

            validation = validate_all_timeframes({"4h": df_4h}, coin)
            if not validation["valid"]:
                continue

            d4h       = calculate_all(validation["klines"]["4h"], timeframe="4h")
            direction = machine.context.get("direction")
            price     = d4h.get("price", 0)

            if not direction:
                machine.bias_lost()
                state_manager._persist(coin)
                continue

            zone = get_active_zone(d4h, direction)

            if machine.state == "zone_active" and not zone:
                machine.zone_invalidated()
                state_manager._persist(coin)
                log.info("%s zone no longer valid — back to bias_defined", coin)
                _write_coin_cache(
                    coin          = coin,
                    machine_state = machine.state,
                    context       = machine.context,
                    price         = price,
                    ttl           = 300,
                )
                continue

            if not zone:
                log.debug("%s no active zone found", coin)
                _write_coin_cache(
                    coin          = coin,
                    machine_state = machine.state,
                    context       = machine.context,
                    price         = price,
                    ttl           = 300,
                )
                continue

            d1h = calculate_all(
                load_candles(coin, "1h", limit=300), timeframe="1h"
            ) if df_1h is not None else {}

            state_manager.update_context(coin, {
                "zone":            zone,
                "d4h":             d4h,
                "d4h_price":       price,
                "atr_4h":          d4h.get("atr"),
                "d1h":             d1h,
                "zone_updated_at": time.time(),
            })

            if machine.state == "bias_defined":
                machine.zone_found()
                state_manager._persist(coin)

            _write_coin_cache(
                coin          = coin,
                machine_state = machine.state,
                context       = machine.context,
                price         = price,
                ttl           = 300,
            )

        except Exception as e:
            log.error("Zone update failed %s: %s", coin, e)

    log.info("Zone update complete")


async def run_trigger_check():
    active_coins = [
        coin for coin in cfg.COINS
        if state_manager.get_state(coin) == "zone_active"
    ]

    if not active_coins:
        return

    log.info("Trigger check — %s active coins", len(active_coins))

    for coin in active_coins:
        try:
            machine   = state_manager.get(coin)
            context   = machine.context
            zone      = context.get("zone")
            direction = context.get("direction")
            atr_4h    = context.get("atr_4h") or 0

            if not zone or not direction or not atr_4h:
                machine.zone_invalidated()
                state_manager._persist(coin)
                continue

            df_15m = await get_15m_data(coin)
            if df_15m is None or len(df_15m) < 10:
                continue

            current_price = float(df_15m["close"].iloc[-1])
            distance_pct  = abs(current_price - zone["mid"]) / current_price * 100
            max_distance  = zone.get("max_distance", 3.0)

            if distance_pct > max_distance * 1.5:
                machine.zone_invalidated()
                state_manager._persist(coin)
                log.info("%s price moved away from zone — invalidated", coin)
                continue

            trigger = check_15m_trigger(
                df_15m    = df_15m,
                zone      = zone,
                direction = direction,
                atr_4h    = atr_4h,
            )

            if not trigger["confirmed"]:
                continue

            df_4h = load_candles(coin, "4h", limit=500)
            if df_4h is None:
                continue

            d4h = calculate_all(df_4h, timeframe="4h")
            d1h = context.get("d1h") or {}

            risk = validate_risk(
                entry     = trigger["entry_price"],
                zone      = zone,
                direction = direction,
                d4h       = d4h,
                d1h       = d1h,
            )

            if not risk["valid"]:
                log.info("%s trigger confirmed but risk invalid: %s", coin, risk["reason"])
                continue

            state_manager.update_context(coin, {
                "trigger_pattern": trigger["pattern"],
                "entry_price":     trigger["entry_price"],
                "candle_low":      trigger.get("candle_low"),
                "candle_high":     trigger.get("candle_high"),
                "sl":              risk["sl"],
                "tp1":             risk["tp1"],
                "tp2":             risk.get("tp2"),
                "rr":              risk["rr"],
                "rr_valid":        risk["rr"] >= cfg.SIGNAL_ENGINE["min_rr"],
                "triggered_at":    time.time(),
            })

            machine.trigger_confirmed()
            state_manager._persist(coin)

            signal = build_signal(coin, machine.context, d1h, d4h)
            if not signal:
                machine.zone_invalidated()
                state_manager._persist(coin)
                continue

            session = get_session()
            signal["session_name"] = session["name"]

            _write_coin_cache(
                coin          = coin,
                machine_state = machine.state,
                context       = machine.context,
                signal        = signal,
                price         = current_price,
                ttl           = 1800,
            )

            db_id = save_signal_to_db(signal, coin, session)

            if db_id:
                signal["db_id"] = db_id
                _write_signal_to_redis(coin, signal, db_id)

                if cfg.CONTENT_ENABLED and signal.get("grade") in ("A+", "A"):
                    asyncio.create_task(_run_content(db_id))

                await send_signal(signal, coin, signal.get("bias_strength", ""), session["name"])
                await _open_trade(coin, signal, db_id)

        except Exception as e:
            log.error("Trigger check failed %s: %s", coin, e)

    _write_active_pairs_to_redis()


async def _run_content(db_id: int):
    try:
        from content.pipeline import run_content_pipeline
        await run_content_pipeline(db_id)
    except Exception as e:
        log.error("Content pipeline error: %s", e)


async def scan_all_coins() -> list:
    log.info("Manual scan triggered")
    await run_daily_bias_update()
    await run_zone_update()
    await run_trigger_check()

    results = []
    for coin in cfg.COINS:
        machine = state_manager.get(coin)
        results.append({
            "coin":      coin,
            "state":     machine.state,
            "direction": machine.context.get("direction", ""),
            "grade":     machine.context.get("grade",     ""),
            "score":     machine.context.get("score",     0),
        })

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    await send_scan_summary(results)

    from events import emit
    asyncio.create_task(emit("scan_complete"))
    return results


def get_db_stats() -> dict:
    try:
        with get_db_session() as db:
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
        log.error("Stats error: %s", e)
        return {}