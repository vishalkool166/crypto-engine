import asyncio
import logging
import time
import json
from config import cfg
from data.cache import cache
from data.store import load_candles
from data.fetcher import get_15m_data, get_ticker, get_funding_rate
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


def _build_partial_score(machine_state: str, context: dict) -> float:
    bias = context.get("bias", {})
    zone = context.get("zone", {})

    if machine_state == "no_bias":
        return 0

    score = 0.0

    strength = bias.get("strength", "weak") if bias else "weak"
    if strength == "strong":
        score += 30
    elif strength == "moderate":
        score += 20
    else:
        score += 10

    sweep_score = bias.get("sweep_score", 0) if bias else 0
    score += min(sweep_score * 2, 20)

    if bias.get("displacement"):
        if bias.get("displacement_strong"):
            score += 15
        else:
            score += 8

    if machine_state in ("zone_active", "signal_ready"):
        dist     = zone.get("distance_pct", 99) if zone else 99
        max_dist = zone.get("max_distance", 3.0) if zone else 3.0
        if max_dist > 0:
            proximity = max(0, 1 - (dist / max_dist))
            score += round(proximity * 20)

        touches = zone.get("touch_count", 0) if zone else 0
        if touches == 0:
            score += 5
        elif touches == 1:
            score += 3

    if machine_state == "signal_ready":
        score += 10

    return min(round(score), 99)


def _build_factor_scores(machine_state: str, context: dict) -> list:
    bias = context.get("bias", {})
    zone = context.get("zone", {})
    d1d  = context.get("d1d", {})

    factors = []

    sweep_raw   = bias.get("sweep_score", 0) if bias else 0
    sweep_max   = 12
    sweep_pct   = round(min(sweep_raw / sweep_max, 1) * 100)
    sweep_age   = bias.get("sweep_age_hours", 999) if bias else 999
    sweep_label = bias.get("sweep_label", "No sweep") if bias else "No sweep"
    sweep_desc  = f"{sweep_label} · {sweep_age:.0f}h ago" if bias and bias.get("sweep_detected") else "No sweep detected"
    factors.append({
        "key":    "liquidity_sweep",
        "label":  "Liquidity Sweep",
        "earned": min(sweep_raw, sweep_max),
        "max":    sweep_max,
        "pct":    sweep_pct,
        "pass":   sweep_raw >= 3,
        "detail": sweep_desc,
    })

    disp_atr    = bias.get("displacement_atr", 0) if bias else 0
    disp_conf   = bias.get("displacement", False) if bias else False
    disp_strong = bias.get("displacement_strong", False) if bias else False
    disp_earned = 11 if disp_strong else 7 if disp_conf else 0
    disp_max    = 11
    disp_pct    = round(disp_earned / disp_max * 100)
    disp_desc   = (
        f"Strong displacement {disp_atr:.1f}x ATR" if disp_strong else
        f"Moderate displacement {disp_atr:.1f}x ATR" if disp_conf else
        "No displacement confirmed"
    )
    factors.append({
        "key":    "displacement",
        "label":  "Displacement",
        "earned": disp_earned,
        "max":    disp_max,
        "pct":    disp_pct,
        "pass":   disp_conf,
        "detail": disp_desc,
    })

    ob_earned = 0
    ob_max    = 10
    ob_desc   = "No zone identified"
    if zone and machine_state in ("zone_active", "signal_ready", "trade_active"):
        strength  = float(zone.get("strength", 0))
        touches   = int(zone.get("touch_count", 0))
        in_zone   = zone.get("in_zone", False)
        zone_type = zone.get("type", "OB")
        dist      = zone.get("distance_pct", 99)
        max_dist  = zone.get("max_distance", 3.0)

        if in_zone:
            ob_earned = 10
        elif dist <= max_dist:
            proximity = max(0, 1 - (dist / max_dist))
            ob_earned = round(proximity * 8)
        else:
            ob_earned = 2

        touch_penalty = touches * 2
        ob_earned     = max(0, ob_earned - touch_penalty)
        ob_desc       = (
            f"{zone_type} zone · "
            f"{'In zone' if in_zone else f'{dist:.2f}% away'} · "
            f"{touches} touch{'es' if touches != 1 else ''}"
        )

    factors.append({
        "key":    "order_blocks",
        "label":  "Order Block / FVG",
        "earned": ob_earned,
        "max":    ob_max,
        "pct":    round(ob_earned / ob_max * 100),
        "pass":   ob_earned >= 5,
        "detail": ob_desc,
    })

    rt_earned = 0
    rt_max    = 10
    rt_desc   = "No retest zone"
    if zone and machine_state in ("zone_active", "signal_ready", "trade_active"):
        touches  = int(zone.get("touch_count", 0))
        in_zone  = zone.get("in_zone", False)
        dist     = zone.get("distance_pct", 99)
        max_dist = zone.get("max_distance", 3.0)

        if machine_state == "signal_ready":
            rt_earned = 10
            rt_desc   = "Retest confirmed — rejection pattern detected"
        elif in_zone:
            rt_earned = 7
            rt_desc   = "Price inside zone — awaiting rejection"
        elif dist <= max_dist:
            proximity = max(0, 1 - (dist / max_dist))
            rt_earned = round(proximity * 5)
            rt_desc   = f"Approaching zone — {dist:.2f}% away"
        else:
            rt_earned = 2
            rt_desc   = "Zone identified but price not near"

    factors.append({
        "key":    "retest_confirmation",
        "label":  "Retest / Rejection",
        "earned": rt_earned,
        "max":    rt_max,
        "pct":    round(rt_earned / rt_max * 100),
        "pass":   rt_earned >= 7,
        "detail": rt_desc,
    })

    struct_bias = d1d.get("structure", {}).get("struct_bias", "neutral") if d1d else "neutral"
    direction   = context.get("direction", "")
    d1_cls      = d1d.get("trend", {}).get("cls", "neutral") if d1d else "neutral"

    if (direction == "LONG"  and struct_bias == "bull") or \
       (direction == "SHORT" and struct_bias == "bear"):
        ms_earned = 9
        ms_desc   = f"Structure {struct_bias}ish — aligned with {direction}"
    elif struct_bias == "neutral":
        ms_earned = 4
        ms_desc   = "Structure neutral — no clear bias"
    else:
        ms_earned = 1
        ms_desc   = f"Structure {struct_bias}ish — conflicts with {direction}"

    ms_max = 9
    factors.append({
        "key":    "market_structure",
        "label":  "Market Structure",
        "earned": ms_earned,
        "max":    ms_max,
        "pct":    round(ms_earned / ms_max * 100),
        "pass":   ms_earned >= 7,
        "detail": ms_desc,
    })

    return factors


def _get_live_market(coin: str, fallback_price: float = 0, df_1d=None) -> dict:
    price = fallback_price

    try:
        from trade.ws import get_mark_price
        live = get_mark_price(coin)
        if live and live > 0:
            price = live
    except Exception:
        pass

    change24 = 0.0
    if df_1d is not None and len(df_1d) >= 2:
        try:
            prev_close = float(df_1d.iloc[-2]["close"])
            curr_close = float(df_1d.iloc[-1]["close"])
            if prev_close > 0:
                change24 = round((curr_close - prev_close) / prev_close * 100, 2)
        except Exception:
            pass

    funding = 0.0
    try:
        from redis_client import get_redis
        r = get_redis()
        if r:
            raw = r.get(f"funding:{coin}USDT")
            if raw:
                funding = float(raw)
    except Exception:
        pass

    return {
        "price":       price,
        "change24":    change24,
        "funding":     funding,
        "oi":          0,
        "oi_change":   0,
        "long_ratio":  50,
        "short_ratio": 50,
        "change_pos":  change24 >= 0,
    }


def _write_coin_cache(
    coin:          str,
    machine_state: str,
    context:       dict,
    signal:        dict | None = None,
    price:         float       = 0,
    ttl:           int         = 900,
    df_1d                      = None,
):
    try:
        zone      = context.get("zone", {})
        bias      = context.get("bias", {})
        direction = context.get("direction", "--")

        if signal:
            display_score     = signal.get("score", 0)
            display_grade     = signal.get("grade", "--")
            display_direction = signal.get("direction", direction)
        else:
            display_score     = _build_partial_score(machine_state, context)
            display_grade     = "--"
            display_direction = direction if direction != "--" else "--"

        if bias and bias.get("valid"):
            regime_str = f"{bias.get('direction','--')} · {bias.get('strength','--')}"
        else:
            regime_str = machine_state.replace("_", " ") if machine_state != "no_bias" else "--"

        factors    = _build_factor_scores(machine_state, context)
        max_weight = sum(f["max"] for f in factors)
        total_earned = sum(f["earned"] for f in factors)
        norm_score = round(total_earned / max_weight * 100) if max_weight > 0 else 0

        market = _get_live_market(coin, price, df_1d)

        sweep_data = {
            "detected":  bias.get("sweep_detected", False) if bias else False,
            "confirmed": bias.get("sweep_detected", False) if bias else False,
            "score":     bias.get("sweep_score",    0)     if bias else 0,
            "label":     bias.get("sweep_label",    "")    if bias else "",
            "age_hours": bias.get("sweep_age_hours", 0)    if bias else 0,
        }

        thesis = ""
        if signal:
            thesis = signal.get("narrative", "")
        elif bias and bias.get("valid"):
            parts = []
            if bias.get("sweep_detected"):
                parts.append(
                    f"✔ {bias.get('sweep_label','Sweep')} detected "
                    f"{bias.get('sweep_age_hours',0):.0f}h ago"
                )
            if bias.get("displacement"):
                parts.append(
                    f"✔ Displacement confirmed "
                    f"{bias.get('displacement_atr',0):.1f}x ATR"
                )
            if zone and machine_state in ("zone_active", "signal_ready"):
                parts.append(
                    f"✔ {zone.get('type','Zone')} identified "
                    f"at {zone.get('bottom',0):.4f}–{zone.get('top',0):.4f}"
                )
            if machine_state == "zone_active":
                parts.append(
                    f"⏳ Watching for 15M rejection trigger"
                )
            thesis = "\n".join(parts)

        entry = {
            "coin":      coin,
            "grade":     display_grade,
            "direction": display_direction,
            "score":     display_score,
            "state":     machine_state,
            "signal":    signal or {},
            "market":    market,
            "regime":    regime_str,
            "session":   get_session().get("name", "--"),
            "sweep":     sweep_data,
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
                "thesis":           thesis,
                "confidence_label": (
                    signal.get("grade", "") if signal
                    else bias.get("strength", "").title() if bias and bias.get("valid")
                    else ""
                ),
            },
            "actual_rr":      signal.get("actual_rr", 0) if signal else 0,
            "ml_probability": None,
            "cached_at":      time.time(),
            "wconf": {
                "factors":      factors,
                "norm_score":   norm_score,
                "market_score": norm_score,
                "entry_score":  norm_score,
                "btc_score":    0,
            },
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


async def run_market_data_update():
    for coin in cfg.COINS:
        try:
            machine = state_manager.get(coin)
            context = machine.context
            cached  = cache.get_raw(f"signal_{coin}")
            if not cached:
                continue

            try:
                from trade.ws import get_mark_price
                live = get_mark_price(coin)
                if live and live > 0:
                    cached["market"]["price"] = live
            except Exception:
                pass

            try:
                ticker = await get_ticker(coin)
                if ticker:
                    cached["market"]["change24"]   = float(ticker.get("percentage") or 0)
                    cached["market"]["change_pos"] = float(ticker.get("percentage") or 0) >= 0
            except Exception:
                pass

            try:
                funding = await get_funding_rate(coin)
                cached["market"]["funding"] = funding
            except Exception:
                pass

            cache.set(f"signal_{coin}", cached, ttl=900)

        except Exception as e:
            log.error("Market data update failed %s: %s", coin, e)


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
                    df_1d         = klines["1d"],
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
                df_1d         = klines["1d"],
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

            df_1d_cached = load_candles(coin, "1d", limit=10)

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
                    df_1d         = df_1d_cached,
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
                    df_1d         = df_1d_cached,
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
                df_1d         = df_1d_cached,
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

            df_1d_cached = load_candles(coin, "1d", limit=10)

            _write_coin_cache(
                coin          = coin,
                machine_state = machine.state,
                context       = machine.context,
                signal        = signal,
                price         = current_price,
                ttl           = 1800,
                df_1d         = df_1d_cached,
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
    await run_market_data_update()

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