import asyncio
import logging
import time
import json
from config import cfg
from data.cache import cache
from engines.validator import validate_all_timeframes
from database import get_session, Signal as SignalModel
from engines.indicators import calculate_all
from engines.regime import detect_regime, assess_btc_stability
from engines.sweep import detect_sweep
from engines.displacement import detect_displacement
from engines.retest import detect_retest
from engines.confluence import score_confluence
from engines.signal import (
    get_tier, get_session as get_trading_session,
    run_no_trade_engine, generate_signal
)
from alerts.telegram import send_signal, send_scan_summary
from alerts.utils import categorize_results
from content.pipeline import run_content_pipeline, run_commentary_pipeline

log = logging.getLogger(__name__)

CACHE_TTL           = 1500
ENTRY_PRICE_TOL     = 0.003
MAX_ENTRY_DEVIATION = 0.01

_scan_running   = False
_scan_semaphore = asyncio.Semaphore(3)


def _interpret_oi(market: dict) -> dict:
    fund = market["funding"] * 100
    pu   = market["change24"] > 0
    oiu  = market["oi_change"] > 1

    bullish_confirm = pu and oiu
    bearish_confirm = (not pu) and oiu

    oi_change = market.get("oi_change", 0)
    oi_flat   = abs(oi_change) <= 1

    if bullish_confirm:
        primary_score = 7
        primary_label = "OI bullish confirm"
    elif bearish_confirm:
        primary_score = 7
        primary_label = "OI bearish confirm"
    elif oi_flat:
        primary_score = 5
        primary_label = "OI neutral"
    else:
        primary_score = 3
        primary_label = "OI exhaustion"

    funding_score = (
        0 if abs(fund) > 0.08 else
        3 if abs(fund) > 0.05 else 6
    )

    crowding = ""
    lr = market["long_ratio"]
    sr = market["short_ratio"]
    if lr > 68:
        crowding = f"🚨 {lr:.1f}% longs — dangerous"
    elif lr > 62:
        crowding = f"⚠️ {lr:.1f}% longs — elevated"
    elif sr > 68:
        crowding = f"🚨 {sr:.1f}% shorts — dangerous"
    elif sr > 62:
        crowding = f"⚠️ {sr:.1f}% shorts — elevated"

    return {
        "primary_score":    primary_score,
        "primary_label":    primary_label,
        "funding_score":    funding_score,
        "funding_warning": (
            f"🚨 Extreme funding {fund:.4f}%"
            if abs(fund) > 0.08 else
            f"⚠️ Elevated funding {fund:.4f}%"
            if abs(fund) > 0.05 else ""
        ),
        "crowding_warning": crowding
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
        log.error(f"ML gate error: {e}")
        return True, 1.0


def save_signal_to_db(signal, coin, regime, session, sweep,
                      retest, disp, market, wconf=None) -> int:
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
                SignalModel.outcome   == "pending"
            ).first()

            if existing:
                log.debug(f"Skipping duplicate signal — {coin} {signal['direction']} already pending id:{existing.id}")
                return existing.id

            factor_scores_json = None
            if wconf and wconf.get("factors"):
                factor_scores_json = json.dumps({
                    f["key"]: f["earned"] for f in wconf["factors"]
                })

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
                leverage      = str(cfg.LEVERAGE) + "x" if hasattr(cfg, "LEVERAGE") else "10x",
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
            log.info(f"Signal saved — ID:{row.id} {coin} Grade:{signal['grade']} TP:{signal.get('tp1')}")
            return row.id

    except Exception as e:
        log.error(f"DB save error: {e}")
        return None


async def _send_to_freqtrade(signal: dict, coin: str, db_id: int) -> bool:
    try:
        from api.freqtrade import ft_force_enter, ft_has_open_trade, ft_open_trade_count

        if await ft_has_open_trade(coin):
            log.info(f"Skipping forceenter — {coin} already has open trade")
            return False

        open_count = await ft_open_trade_count()
        max_trades = cfg.MAX_TRADES_PER_DAY
        if open_count >= max_trades:
            log.info(f"Skipping forceenter — max open trades reached ({open_count}/{max_trades})")
            return False

        direction = signal.get("direction", "")
        side      = "short" if direction == "SHORT" else "long"
        entry     = float(signal.get("entry", 0))
        sl        = float(signal.get("sl", 0))
        tp        = float(signal.get("tp1", 0))
        grade     = signal.get("grade", "")
        risk_amt  = float(signal.get("risk_amt", 0))
        leverage  = cfg.LEVERAGE

        stake = risk_amt * leverage

        if not entry or not sl or not tp:
            log.error(f"Invalid signal levels for {coin} — entry:{entry} sl:{sl} tp:{tp}")
            return False

        result = await ft_force_enter(
            coin      = coin,
            side      = side,
            entry     = entry,
            sl        = sl,
            tp        = tp,
            leverage  = leverage,
            stake     = stake,
            signal_id = db_id,
            grade     = grade
        )

        if result.get("success"):
            log.info(f"Trade opened via forceenter: {coin} {direction} trade_id:{result.get('trade_id')}")
            return True
        else:
            log.error(f"forceenter failed: {coin} — {result.get('error')}")
            return False

    except Exception as e:
        log.error(f"_send_to_freqtrade error {coin}: {e}")
        return False


async def analyze_coin(
    coin:     str,
    capital:  float = None,
    leverage: int   = None
) -> dict:
    async with _scan_semaphore:
        return await _analyze_coin_inner(coin, capital, leverage)


async def _analyze_coin_inner(
    coin:     str,
    capital:  float = None,
    leverage: int   = None
) -> dict:

    capital  = capital  or cfg.CAPITAL
    leverage = leverage or cfg.LEVERAGE

    cached = cache.get(f"signal_{coin}")
    if cached:
        return cached

    try:
        from data.fetcher import get_all_data
        raw = await get_all_data(coin)
    except Exception as e:
        log.error(f"Data fetch failed {coin}: {e}")
        return {"coin": coin, "error": str(e)}

    klines      = raw["klines"]
    news_filter = raw["news_filter"]
    df_15m      = raw.get("klines_15m")

    validation = validate_all_timeframes(klines, coin)
    if not validation["valid"]:
        error_msg = " | ".join(validation["errors"])
        log.error(f"Data validation failed: {coin} — {error_msg}")
        return {"coin": coin, "error": f"Data quality failure: {error_msg}"}

    klines = validation["klines"]

    d1w = calculate_all(klines["1w"])
    d1d = calculate_all(klines["1d"])
    d4h = calculate_all(klines["4h"])
    d1h = calculate_all(klines["1h"])

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
            btc_data    = btc_cached
            btc_4h_data = btc_4h_cached
        else:
            try:
                from data.fetcher import get_all_data
                btc_raw     = await get_all_data("BTC")
                btc_data    = calculate_all(btc_raw["klines"]["1d"])
                btc_4h_data = calculate_all(btc_raw["klines"]["4h"])
                cache.set("btc_1d_data", btc_data,    ttl=900)
                cache.set("btc_4h_data", btc_4h_data, ttl=900)
            except Exception:
                btc_data    = None
                btc_4h_data = None

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
        "fear_greed":  {"value": 50, "label": "Neutral"}
    }

    key_levels = _extract_key_levels(klines["1d"], klines["1w"])
    session    = get_trading_session(vol_ratio=vol_ratio)
    regime     = detect_regime(d1d, d4h)

    sweep  = detect_sweep(klines["1d"], key_levels, d1d.get("atr", 0), d1d["swings"])
    disp   = detect_displacement(klines["4h"], d4h.get("atr", 0))
    retest = detect_retest(klines["4h"], d4h, sweep, disp, d1h=d1h, d1d=d1d)

    oi_matrix = _interpret_oi(market)

    wconf = score_confluence(
        d1w, d1d, d4h, d1h,
        market, key_levels,
        session, btc_data,
        btc_inst, regime,
        sweep, disp,
        retest, oi_matrix,
        coin,
        btc_4h=btc_4h_data
    )

    no_trade = run_no_trade_engine(
        regime, d1d, d4h,
        market, session,
        sweep, disp,
        retest, btc_data,
        btc_inst, oi_matrix,
        news_filter,
        wconf["norm_score"],
        coin=coin,
        d1w=d1w,
        wconf=wconf
    )

    signal = generate_signal(
        d1d          = d1d,
        d4h          = d4h,
        wconf        = wconf,
        no_trade     = no_trade,
        market       = market,
        key_levels   = key_levels,
        capital      = capital,
        leverage     = leverage,
        df_15m       = df_15m,
        sweep        = sweep,
        displacement = disp,
        retest       = retest,
        btc_data     = btc_data,
        btc_inst     = btc_inst,
        oi_matrix    = oi_matrix,
        regime       = regime,
        session      = session,
        d1w          = d1w
    )

    signal["sweep_score"] = sweep.get("score", 0)
    signal["disp_score"]  = disp.get("score", 0)
    signal["funding"]     = raw["funding"]
    signal["coin"]        = coin

    db_id = save_signal_to_db(
        signal=signal, coin=coin,
        regime=regime["label"], session=session["name"],
        sweep=sweep, retest=retest, disp=disp,
        market=market, wconf=wconf
    )

    if db_id:
        signal["db_id"] = db_id

        if cfg.CONTENT_ENABLED and signal.get("grade") in ["A+", "A"]:
            asyncio.create_task(run_content_pipeline(db_id))

        if signal.get("grade") in cfg.MIN_GRADE_TO_TRADE and \
           signal.get("direction") in ["LONG", "SHORT"] and \
           signal.get("entry"):

            ml_passed, ml_prob = _check_ml_gate(signal, wconf)

            if ml_passed:
                asyncio.create_task(
                    _send_to_freqtrade(signal, coin, db_id)
                )
                log.info(
                    f"Signal forwarded to Freqtrade via forceenter: {coin} "
                    f"Grade:{signal.get('grade')} "
                    f"ML_prob:{ml_prob:.2f} "
                    f"RR:{signal.get('actual_rr')}"
                )
            else:
                log.info(
                    f"Signal ML-filtered: {coin} "
                    f"Grade:{signal.get('grade')} "
                    f"ML_prob:{ml_prob:.2f} — not forwarded"
                )

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
        "ml_probability":    signal.get("ml_probability", None),
        "actual_rr":         signal.get("actual_rr", 0),
        "tp_mult":           signal.get("tp_mult", 2.0),
        "cached_at":         time.time(),
        "data_quality": {
            tf: {
                "valid":   r["valid"],
                "clean":   r["clean"],
                "issues":  r["issues"],
                "removed": r["removed"]
            }
            for tf, r in validation["reports"].items()
        }
    }

    cache.set(f"signal_{coin}", result, ttl=CACHE_TTL)

    if signal.get("grade") in cfg.MIN_GRADE_TO_TRADE:
        if signal.get("direction") in ["LONG", "SHORT"]:
            await send_signal(signal, coin, regime["label"], session["name"])

    return result


async def scan_all_coins() -> list:
    global _scan_running

    if _scan_running:
        log.info("Scan already running — skipping")
        return []

    _scan_running = True
    results       = []

    try:
        log.info(f"Scan started — {len(cfg.COINS)} coins")

        btc_cached = cache.get_raw("btc_1d_data")
        if not btc_cached:
            try:
                from data.fetcher import get_all_data
                btc_raw        = await get_all_data("BTC")
                btc_validation = validate_all_timeframes(btc_raw["klines"], "BTC")
                if btc_validation["valid"]:
                    btc_data    = calculate_all(btc_validation["klines"]["1d"])
                    btc_4h_data = calculate_all(btc_validation["klines"]["4h"])
                    cache.set("btc_1d_data", btc_data,    ttl=900)
                    cache.set("btc_4h_data", btc_4h_data, ttl=900)
            except Exception as e:
                log.warning(f"BTC pre-fetch failed: {e}")

        tasks        = [_scan_coin_safe(coin) for coin in cfg.COINS]
        scan_results = await asyncio.gather(*tasks)

        for r in scan_results:
            if r and "error" not in r:
                results.append(r)

        results.sort(key=lambda x: x.get("score", 0), reverse=True)

        _write_active_pairs_to_redis()

        tradeable = [
            r for r in results
            if r.get("grade") in ["A+", "A"] and
            r.get("direction") in ["LONG", "SHORT"]
        ]

        if not tradeable and cfg.CONTENT_ENABLED and results:
            asyncio.create_task(run_commentary_pipeline(results))

        await send_scan_summary(results)

        from events import emit
        asyncio.create_task(emit("scan_complete"))

        log.info(f"Scan complete — {len(results)} coins")

    finally:
        _scan_running = False

    return results


def _write_active_pairs_to_redis():
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return

        pairs   = [f"{coin}/USDT:USDT" for coin in cfg.COINS]
        payload = json.dumps({"pairs": pairs, "refresh_period": 1800})
        r.setex("pairs:active", 1800, payload)
        log.info(f"Active pairs written to Redis: {len(pairs)} pairs")

    except Exception as e:
        log.error(f"Redis active pairs write failed: {e}")


async def _scan_coin_safe(coin: str) -> dict:
    try:
        r = await analyze_coin(coin)
        await asyncio.sleep(0.5)
        return r
    except Exception as e:
        log.error(f"Scan error {coin}: {e}")
        return None


def _check_heartbeat():
    import runtime_state as rs
    last = rs.get_last_signal_time()
    if last == 0:
        rs.set_last_signal_time(time.time())
        return
    hours_since = (time.time() - last) / 3600
    if hours_since >= 3:
        rs.set_last_signal_time(time.time())
        asyncio.create_task(_send_heartbeat(hours_since))


async def _send_heartbeat(hours: float):
    try:
        from alerts.telegram import send
        await send(
            f"💓 *Bot Heartbeat*\n\n"
            f"No tradeable signals in `{hours:.1f}h`.\n"
            f"Bot alive and scanning every 15 minutes."
        )
    except Exception:
        pass


def get_db_stats() -> dict:
    try:
        with get_session() as db:
            all_sigs = db.query(SignalModel).all()
            closed   = [s for s in all_sigs if s.outcome not in ["pending", None]]
            wins     = [s for s in closed if s.outcome == "win"]

            by_grade = {}
            for g in ["A+", "A", "B"]:
                g_trades = [s for s in closed if s.grade == g]
                g_wins   = [s for s in g_trades if s.outcome == "win"]
                by_grade[g] = {
                    "total":     len(g_trades),
                    "wins":      len(g_wins),
                    "losses":    len(g_trades) - len(g_wins),
                    "win_rate":  round(len(g_wins) / len(g_trades) * 100, 1) if g_trades else 0,
                    "total_pnl": round(sum(s.pnl or 0 for s in g_trades), 2)
                }

            return {
                "total":     len(all_sigs),
                "closed":    len(closed),
                "pending":   len(all_sigs) - len(closed),
                "wins":      len(wins),
                "losses":    len(closed) - len(wins),
                "win_rate":  round(len(wins) / len(closed) * 100, 1) if closed else 0,
                "total_pnl": round(sum(s.pnl or 0 for s in closed), 2),
                "by_grade":  by_grade
            }

    except Exception as e:
        log.error(f"Stats error: {e}")
        return {}