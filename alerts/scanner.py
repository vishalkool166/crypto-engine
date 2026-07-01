import asyncio
import logging
import time
import json
from config import cfg, SIGNAL_CACHE_TTL
from data.cache import cache
from engines.validator import validate_all_timeframes
from database import get_session, Signal as SignalModel
from engines.indicators import calculate_all
from engines.regime import detect_regime, assess_btc_stability
from engines.sweep import detect_sweep
from engines.displacement import detect_displacement
from engines.retest import detect_retest
from engines.confluence import score_confluence
from engines.signal import get_session as get_trading_session, run_no_trade_engine, generate_signal
from engines.capital import compute_allocation
from alerts.telegram import send_signal, send_scan_summary
from alerts.utils import categorize_results
from content.pipeline import run_content_pipeline, run_commentary_pipeline

log = logging.getLogger(__name__)

_scan_running   = False
_scan_semaphore = asyncio.Semaphore(3)


def _interpret_oi(market: dict) -> dict:
    fund = market["funding"] * 100
    pu   = market["change24"] > 0
    oiu  = market["oi_change"] > 1
    flat = abs(market.get("oi_change", 0)) <= 1

    if pu and oiu:
        score, label = 7, "OI bullish confirm"
    elif not pu and oiu:
        score, label = 7, "OI bearish confirm"
    elif flat:
        score, label = 5, "OI neutral"
    else:
        score, label = 3, "OI exhaustion"

    funding_score = 0 if abs(fund) > 0.08 else 3 if abs(fund) > 0.05 else 6

    lr = market["long_ratio"]
    sr = market["short_ratio"]
    crowding = (
        f"🚨 {lr:.1f}% longs — dangerous" if lr > 68 else
        f"⚠️ {lr:.1f}% longs — elevated"  if lr > 62 else
        f"🚨 {sr:.1f}% shorts — dangerous" if sr > 68 else
        f"⚠️ {sr:.1f}% shorts — elevated"  if sr > 62 else ""
    )

    return {
        "primary_score":    score,
        "primary_label":    label,
        "funding_score":    funding_score,
        "funding_warning":  (
            f"🚨 Extreme funding {fund:.4f}%" if abs(fund) > 0.08 else
            f"⚠️ Elevated funding {fund:.4f}%" if abs(fund) > 0.05 else ""
        ),
        "crowding_warning": crowding,
    }


def _extract_key_levels(d1d_df, d1w_df) -> dict:
    return {
        "pdh": float(d1d_df.iloc[-2]["high"])  if len(d1d_df) >= 2 else 0,
        "pdl": float(d1d_df.iloc[-2]["low"])   if len(d1d_df) >= 2 else 0,
        "pdc": float(d1d_df.iloc[-2]["close"]) if len(d1d_df) >= 2 else 0,
        "pwh": float(d1w_df.iloc[-2]["high"])  if len(d1w_df) >= 2 else 0,
        "pwl": float(d1w_df.iloc[-2]["low"])   if len(d1w_df) >= 2 else 0,
    }


def _check_ml_gate(signal: dict, wconf: dict) -> tuple[bool, float]:
    if not cfg.ML_ENABLED:
        return True, 1.0
    try:
        from ml.predictor import is_ml_approved
        approved, prob = is_ml_approved(signal, wconf)
        signal["ml_probability"] = prob
        return approved, prob
    except Exception as e:
        log.error("ML gate error: %s", e)
        return True, 1.0


def _write_signal_to_redis(coin: str, signal: dict, db_id: int) -> None:
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


def _write_active_pairs_to_redis() -> None:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return
        pairs = [f"{coin}/USDT:USDT" for coin in cfg.COINS]
        r.setex("pairs:active", 1800, json.dumps({"pairs": pairs, "refresh_period": 1800}))
        log.info("Active pairs written to Redis: %s pairs", len(pairs))
    except Exception as e:
        log.error("Redis active pairs write failed: %s", e)


def save_signal_to_db(
    signal: dict,
    coin:   str,
    regime: str,
    session:str,
    sweep:  dict,
    retest: dict,
    disp:   dict,
    market: dict,
    wconf:  dict | None = None,
) -> int | None:
    if signal.get("grade") not in cfg.MIN_GRADE_TO_TRADE:
        return None
    if signal.get("direction") in ["NO TRADE", "WATCH", "SKIP"]:
        return None
    if signal.get("signal_type") in ["SKIP", "WATCH", "HARD_BLOCK"]:
        return None
    if not signal.get("entry"):
        return None

    try:
        with get_session() as db:
            existing = db.query(SignalModel).filter(
                SignalModel.coin      == coin,
                SignalModel.direction == signal["direction"],
                SignalModel.outcome   == "pending",
            ).first()

            if existing:
                from trade.executor import has_open_trade
                if has_open_trade(coin):
                    log.debug("Trade open for %s — keeping signal ID:%s", coin, existing.id)
                    return None
                existing.outcome = "expired"
                log.info("Expired stale signal ID:%s %s — saving fresh", existing.id, coin)

            factor_scores_json = None
            if wconf and wconf.get("factors"):
                factor_scores_json = json.dumps({f["key"]: f["earned"] for f in wconf["factors"]})

            row = SignalModel(
                coin          = coin,
                direction     = signal["direction"],
                grade         = signal["grade"],
                score         = signal["score"],
                signal_type   = signal["signal_type"],
                entry         = signal.get("entry", 0),
                sl            = signal.get("sl", 0),
                tp1           = signal.get("tp1", 0),
                tp2           = None,
                sl_pct        = signal.get("sl_pct", 0),
                risk_amt      = signal.get("risk_amt", 0),
                risk_pct      = signal.get("risk_pct", 0),
                position      = signal.get("pos_size", 0),
                leverage      = str(signal.get("leverage", 10)) + "x",
                regime        = regime,
                session       = session,
                sweep_score   = sweep.get("score", 0),
                retest_score  = retest.get("score", 0),
                disp_score    = disp.get("score", 0),
                funding       = market.get("funding", 0),
                oi_signal     = _interpret_oi(market).get("primary_label", ""),
                outcome       = "pending",
                factor_scores = factor_scores_json,
                market_score  = wconf.get("market_score") if wconf else None,
                entry_score   = wconf.get("entry_score")  if wconf else None,
                atr_at_entry  = signal.get("atr_used"),
                btc_score     = wconf.get("btc_score")    if wconf else None,
            )
            db.add(row)
            db.flush()
            db.refresh(row)
            log.info("Signal saved — ID:%s %s Grade:%s TP:%s", row.id, coin, signal["grade"], signal.get("tp1"))
            return row.id

    except Exception as e:
        log.error("DB save error: %s", e)
        return None


async def _do_open_trade(item: dict) -> bool:
    from trade.executor import open_position, has_open_trade_or_position

    coin       = item["coin"]
    signal     = item["signal"]
    db_id      = item["db_id"]
    allocation = item.get("allocation", {})

    if not signal.get("entry") or not signal.get("sl") or not signal.get("tp1"):
        log.error("Invalid signal levels for %s", coin)
        return False

    if float(allocation.get("stake", 0)) <= 0:
        log.error("Invalid stake for %s", coin)
        return False

    if await has_open_trade_or_position(coin):
        log.info("Skipping %s — already has open trade or position on exchange", coin)
        return False

    result = await open_position(
        coin      = coin,
        direction = signal.get("direction", ""),
        entry     = float(signal.get("entry", 0)),
        sl        = float(signal.get("sl", 0)),
        tp        = float(signal.get("tp1", 0)),
        stake     = float(allocation.get("stake", 0)),
        leverage  = int(allocation.get("leverage", 10)),
        signal_id = db_id,
        grade     = signal.get("grade", ""),
        regime    = item.get("regime", ""),
        session   = item.get("session", ""),
        score     = float(item.get("score", 0)),
    )

    if result.get("success"):
        log.info("Trade opened: %s %s Grade:%s stake:%.2f lev:%dx trade_id:%s",
                 coin, signal.get("direction"), signal.get("grade"),
                 allocation.get("stake", 0), allocation.get("leverage", 10),
                 result.get("trade_id"))
        return True

    if result.get("deviation_rejected"):
        log.info("Trade skipped — entry deviation: %s — %s", coin, result.get("error"))
    else:
        log.error("Trade open failed: %s — %s", coin, result.get("error"))
    return False


async def _execute_priority_entries(pending: list) -> None:
    if not pending:
        return

    from trade.executor import has_open_trade, get_open_trade_count

    log.info("_execute_priority_entries — pending: %s", len(pending))

    grade_order    = {"A+": 0, "A": 1, "B": 2}
    sorted_signals = sorted(pending, key=lambda x: (grade_order.get(x["grade"], 99), -x["score"]))
    open_count     = get_open_trade_count()
    entered_coins: set = set()

    for item in sorted_signals:
        allocation = item.get("allocation", {})
        if allocation.get("skip"):
            log.info("Skipping %s — allocation: %s", item["coin"], allocation.get("reason"))
            continue
        if open_count >= allocation.get("max_trades_allowed", 3):
            log.info("Max trades reached — stopping")
            break
        coin = item["coin"]
        if coin in entered_coins:
            continue
        if await _do_open_trade(item):
            open_count   += 1
            entered_coins.add(coin)

    log.info("Priority entries complete — %s trades opened", len(entered_coins))


async def analyze_coin(coin: str, capital: float = None, leverage: int = None) -> dict:
    async with _scan_semaphore:
        return await _analyze_coin_inner(coin)


async def _analyze_coin_inner(coin: str) -> dict:
    cached = cache.get_raw(f"signal_{coin}")
    if cached:
        return cached

    try:
        from data.fetcher import get_all_data
        raw = await get_all_data(coin)
    except Exception as e:
        log.error("Data fetch failed %s: %s", coin, e)
        return {"coin": coin, "error": str(e)}

    klines      = raw["klines"]
    news_filter = raw["news_filter"]
    df_15m      = raw.get("klines_15m")

    validation = validate_all_timeframes(klines, coin)
    if not validation["valid"]:
        log.error("Data validation failed: %s — %s", coin, " | ".join(validation["errors"]))
        return {"coin": coin, "error": f"Data quality failure: {' | '.join(validation['errors'])}"}

    klines = validation["klines"]
    d1w    = calculate_all(klines["1w"])
    d1d    = calculate_all(klines["1d"])
    d4h    = calculate_all(klines["4h"])
    d1h    = calculate_all(klines["1h"])

    if coin == "BTC":
        btc_data    = d1d
        btc_4h_data = d4h
        btc_inst    = assess_btc_stability(d1d)
        cache.set("btc_1d_data", d1d, ttl=900)
        cache.set("btc_4h_data", d4h, ttl=900)
    else:
        btc_cached    = cache.get_raw("btc_1d_data")
        btc_4h_cached = cache.get_raw("btc_4h_data")
        if btc_cached:
            btc_data, btc_4h_data = btc_cached, btc_4h_cached
        else:
            try:
                from data.fetcher import get_all_data
                btc_raw     = await get_all_data("BTC")
                btc_data    = calculate_all(btc_raw["klines"]["1d"])
                btc_4h_data = calculate_all(btc_raw["klines"]["4h"])
                cache.set("btc_1d_data", btc_data,    ttl=900)
                cache.set("btc_4h_data", btc_4h_data, ttl=900)
            except Exception:
                btc_data = btc_4h_data = None
        btc_inst = assess_btc_stability(btc_data)

    vol_ratio = (
        d4h["cur_vol"] / d4h["vol_ma10"]
        if d4h.get("vol_ma10") and d4h["vol_ma10"] > 0 else 1.0
    )

    market = {
        "price":       raw["price"],
        "change24":    raw["change24"],
        "funding":     raw["funding"],
        "oi":          raw["oi"],
        "oi_change":   raw["oi_change"],
        "long_ratio":  raw["long_ratio"],
        "short_ratio": raw["short_ratio"],
        "fear_greed":  {"value": 50, "label": "Neutral"},
    }

    key_levels = _extract_key_levels(klines["1d"], klines["1w"])
    session    = get_trading_session(vol_ratio=vol_ratio)
    regime     = detect_regime(d1d, d4h)
    sweep      = detect_sweep(klines["1d"], key_levels, d1d.get("atr", 0), d1d["swings"])
    disp       = detect_displacement(klines["4h"], d4h.get("atr", 0))
    retest     = detect_retest(klines["4h"], d4h, sweep, disp, d1h=d1h, d1d=d1d)
    oi_matrix  = _interpret_oi(market)

    wconf = score_confluence(
        d1w, d1d, d4h, d1h, market, key_levels,
        session, btc_data, btc_inst, regime,
        sweep, disp, retest, oi_matrix, coin, btc_4h=btc_4h_data,
    )

    no_trade = run_no_trade_engine(
        regime, d1d, d4h, market, session, sweep, disp,
        retest, btc_data, btc_inst, oi_matrix, news_filter,
        wconf["norm_score"], coin=coin, d1w=d1w, wconf=wconf,
    )

    signal = generate_signal(
        d1d=d1d, d4h=d4h, wconf=wconf, no_trade=no_trade,
        market=market, key_levels=key_levels, df_15m=df_15m,
        sweep=sweep, displacement=disp, retest=retest,
        btc_data=btc_data, btc_inst=btc_inst, oi_matrix=oi_matrix,
        regime=regime, session=session, d1w=d1w, d1h=d1h,
    )

    signal["sweep_score"] = sweep.get("score", 0)
    signal["disp_score"]  = disp.get("score", 0)
    signal["funding"]     = raw["funding"]
    signal["coin"]        = coin

    db_id         = save_signal_to_db(signal, coin, regime["label"], session["name"], sweep, retest, disp, market, wconf)
    pending_entry = None

    if db_id:
        signal["db_id"] = db_id
        _write_signal_to_redis(coin, signal, db_id)

        if cfg.CONTENT_ENABLED and signal.get("grade") in ["A+", "A"]:
            asyncio.create_task(run_content_pipeline(db_id))

        if (signal.get("grade") in cfg.MIN_GRADE_TO_TRADE and
                signal.get("direction") in ["LONG", "SHORT"] and
                signal.get("entry")):

            from trade.executor import has_open_trade_or_position
            if await has_open_trade_or_position(coin):
                log.info("Skipping entry queue — %s already has open trade or position", coin)
            else:
                ml_passed, _ = _check_ml_gate(signal, wconf)
                if ml_passed:
                    allocation = await compute_allocation(
                        signal      = signal,
                        wconf       = wconf,
                        regime      = regime,
                        vol_profile = {
                            "volatility_class": signal.get("vol_class",  "normal"),
                            "atr_pct":          signal.get("atr_pct",    2.0),
                            "adx":              signal.get("adx_used",   20),
                        },
                        direction = signal.get("direction"),
                    )
                    if not allocation.get("skip"):
                        signal.update({
                            "risk_amt": allocation["risk_amt"],
                            "pos_size": allocation["pos_size"],
                            "leverage": allocation["leverage"],
                            "stake":    allocation["stake"],
                        })
                        pending_entry = {
                            "coin":       coin,
                            "grade":      signal.get("grade"),
                            "score":      signal.get("score", 0),
                            "signal":     signal,
                            "db_id":      db_id,
                            "allocation": allocation,
                            "regime":     regime["label"],
                            "session":    session["name"],
                        }
                    else:
                        log.info("Signal %s skipped by allocation: %s", coin, allocation.get("reason"))

    result = {
        "coin":              coin,
        "grade":             signal["grade"],
        "score":             signal["score"],
        "direction":         signal["direction"],
        "signal":            signal,
        "market":            market,
        "regime":            regime["label"],
        "session":           session["name"],
        "d1d":               d1d,
        "d4h":               d4h,
        "d1h":               d1h,
        "d1w":               d1w,
        "key_levels":        key_levels,
        "sweep":             sweep,
        "retest":            retest,
        "displacement":      disp,
        "wconf":             wconf,
        "oi_matrix":         oi_matrix,
        "no_trade":          no_trade,
        "news_filter":       news_filter,
        "explanation":       signal.get("explanation", {}),
        "market_score":      wconf.get("market_score", 0),
        "entry_score":       wconf.get("entry_score",  0),
        "market_blocked":    no_trade.get("market_blocked",    False),
        "entry_blocked":     no_trade.get("entry_blocked",     False),
        "portfolio_blocked": no_trade.get("portfolio_blocked", False),
        "ml_probability":    signal.get("ml_probability"),
        "actual_rr":         signal.get("actual_rr", 0),
        "tp_mult":           signal.get("tp_mult", 2.0),
        "cached_at":         time.time(),
        "pending_entry":     pending_entry,
        "data_quality": {
            tf: {"valid": r["valid"], "clean": r["clean"], "issues": r["issues"], "removed": r["removed"]}
            for tf, r in validation["reports"].items()
        },
    }

    cache.set(f"signal_{coin}", result, ttl=SIGNAL_CACHE_TTL)

    if signal.get("grade") in cfg.MIN_GRADE_TO_TRADE and signal.get("direction") in ["LONG", "SHORT"]:
        await send_signal(signal, coin, regime["label"], session["name"])

    return result


async def scan_all_coins() -> list:
    global _scan_running
    if _scan_running:
        log.info("Scan already running — skipping")
        return []

    _scan_running = True
    results: list = []
    pending: list = []

    try:
        log.info("Scan started — %s coins", len(cfg.COINS))

        if not cache.get_raw("btc_1d_data"):
            try:
                from data.fetcher import get_all_data
                btc_raw = await get_all_data("BTC")
                btc_v   = validate_all_timeframes(btc_raw["klines"], "BTC")
                if btc_v["valid"]:
                    cache.set("btc_1d_data", calculate_all(btc_v["klines"]["1d"]), ttl=900)
                    cache.set("btc_4h_data", calculate_all(btc_v["klines"]["4h"]), ttl=900)
            except Exception as e:
                log.warning("BTC pre-fetch failed: %s", e)

        scan_results = await asyncio.gather(*[_scan_coin_safe(c) for c in cfg.COINS])

        for r in scan_results:
            if r and "error" not in r:
                results.append(r)
                if r.get("pending_entry"):
                    pending.append(r["pending_entry"])

        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        _write_active_pairs_to_redis()

        seen: dict = {}
        for item in pending:
            coin = item["coin"]
            if coin not in seen or item.get("score", 0) > seen[coin].get("score", 0):
                seen[coin] = item
        pending = list(seen.values())

        log.info("Deduplicated pending signals: %s unique coins", len(pending))
        await _execute_priority_entries(pending)

        tradeable = [r for r in results if r.get("grade") in ["A+", "A"] and r.get("direction") in ["LONG", "SHORT"]]
        if not tradeable and cfg.CONTENT_ENABLED and results:
            asyncio.create_task(run_commentary_pipeline(results))

        await send_scan_summary(results)

        from events import emit
        asyncio.create_task(emit("scan_complete"))
        log.info("Scan complete — %s coins", len(results))

    finally:
        _scan_running = False

    return results


async def _scan_coin_safe(coin: str) -> dict | None:
    try:
        r = await analyze_coin(coin)
        await asyncio.sleep(0.5)
        return r
    except Exception as e:
        log.error("Scan error %s: %s", coin, e)
        return None


def get_db_stats() -> dict:
    try:
        with get_session() as db:
            all_sigs = db.query(SignalModel).all()
            closed   = [s for s in all_sigs if s.outcome not in ["pending", None]]
            wins     = [s for s in closed if s.outcome == "win"]
            by_grade = {}
            for g in ["A+", "A", "B"]:
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
        log.error("Stats error: %s", e)
        return {}