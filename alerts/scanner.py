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
from trade.state import state_manager
from trade.manager import trade_manager
import runtime_state as rs

log = logging.getLogger(__name__)

CACHE_TTL       = 1500
TRADE_MAX_AGE   = 300
ENTRY_PRICE_TOL = 0.003
MAX_ENTRY_DEVIATION = 0.01

_scan_running   = False
_scan_semaphore = asyncio.Semaphore(3)


def _interpret_oi(market: dict) -> dict:
    fund = market["funding"] * 100
    pu   = market["change24"] > 0
    oiu  = market["oi_change"] > 1

    bullish_confirm = pu and oiu
    bearish_confirm = (not pu) and oiu
    confirmed       = bullish_confirm or bearish_confirm

    primary_score = 7 if confirmed else 3
    primary_label = (
        "OI bullish confirm"  if bullish_confirm else
        "OI bearish confirm"  if bearish_confirm else
        "OI exhaustion"
    )

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


def _is_cache_fresh_for_trade(cached: dict) -> bool:
    return time.time() - cached.get("cached_at", 0) <= TRADE_MAX_AGE


def _entry_price_valid(signal: dict, current_price: float) -> bool:
    entry     = signal.get("entry", 0)
    direction = signal.get("direction", "")
    if not entry or not current_price:
        return False

    deviation = abs(current_price - entry) / entry

    if deviation > MAX_ENTRY_DEVIATION:
        log.warning(f"Entry too stale: {deviation*100:.2f}% drift — skipping")
        return False

    if direction == "SHORT" and current_price >= entry:
        signal["entry"] = current_price
        log.info(f"SHORT better entry: {entry} → {current_price}")
        return True

    if direction == "LONG" and current_price <= entry:
        signal["entry"] = current_price
        log.info(f"LONG better entry: {entry} → {current_price}")
        return True

    if deviation <= ENTRY_PRICE_TOL:
        return True

    signal["entry"] = current_price
    log.info(f"Entry updated: {entry} → {current_price} ({deviation*100:.2f}% drift)")
    return True


def save_signal_to_db(signal, coin, regime, session, sweep,
                      retest, disp, market, wconf=None) -> int:
    if signal.get("grade") not in ["A+", "A"]:
        return None
    if signal.get("direction") in ["NO TRADE", "WATCH", "SKIP"]:
        return None

    try:
        factor_scores_json = None
        if wconf and wconf.get("factors"):
            factor_scores_json = json.dumps({
                f["key"]: f["earned"] for f in wconf["factors"]
            })

        with get_session() as db:
            row = SignalModel(
                coin          = coin,
                direction     = signal["direction"],
                grade         = signal["grade"],
                score         = signal["score"],
                signal_type   = signal["signal_type"],
                entry         = signal.get("entry", 0),
                sl            = signal.get("sl", 0),
                tp1           = signal.get("tp1", 0),
                tp2           = signal.get("tp2", 0),
                sl_pct        = signal.get("sl_pct", 0),
                risk_amt      = signal.get("risk_amt", 0),
                risk_pct      = signal.get("risk_pct", 0),
                position      = signal.get("pos_size", 0),
                leverage      = str(cfg.LEVERAGE) + "x",
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
            log.info(f"Signal saved — ID:{row.id} {coin} Grade:{signal['grade']}")
            return row.id

    except Exception as e:
        log.error(f"DB save error: {e}")
        return None


async def _attempt_trade(signal: dict, coin: str) -> bool:
    grade     = signal.get("grade")
    direction = signal.get("direction")

    if state_manager.is_paused:
        log.info(f"Auto-execution paused — skipped: {coin}")
        return False

    if grade not in cfg.MIN_GRADE_TO_TRADE:
        return False

    if direction not in ["LONG", "SHORT"]:
        return False

    if not state_manager.can_open_trade():
        log.info(f"Max concurrent trades reached — skipped: {coin}")
        return False

    if signal.get("signal_type") == "PORTFOLIO_BLOCK":
        return False

    from trade.orders import get_current_price
    current_price = get_current_price(coin)
    if not _entry_price_valid(signal, current_price):
        log.warning(f"Entry price stale — skipping {coin}")
        return False

    log.info(f"All gates passed — opening trade: {coin} {direction} Grade:{grade}")
    await trade_manager.open_trade(signal=signal, signal_id=signal.get("db_id"))
    return True


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
    from trade.risk import get_current_tier
    from trade.orders import get_current_price

    tier     = get_current_tier()
    capital  = capital  or tier["balance"] or cfg.CAPITAL
    leverage = leverage or tier["leverage"]

    cached = cache.get(f"signal_{coin}")
    if cached:
        signal        = cached.get("signal", {})
        grade         = signal.get("grade", "F")
        current_price = get_current_price(coin)

        if grade in cfg.MIN_GRADE_TO_TRADE and signal.get("direction") in ["LONG", "SHORT"]:
            if _is_cache_fresh_for_trade(cached) and _entry_price_valid(signal, current_price):
                await _attempt_trade(signal, coin)
                return cached
            else:
                cache.clear(f"signal_{coin}")
        else:
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

    traded = await _attempt_trade(signal, coin)

    if not traded and signal.get("grade") in ["A+", "A"]:
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

        tradeable = [
            r for r in results
            if r.get("grade") in ["A+", "A"] and
            r.get("direction") in ["LONG", "SHORT"]
        ]

        if tradeable:
            rs.set_last_signal_time(time.time())
        else:
            _check_heartbeat()

        await send_scan_summary(results)
        log.info(f"Scan complete — {len(results)} coins")

    finally:
        _scan_running = False

    return results


async def _scan_coin_safe(coin: str) -> dict:
    try:
        r = await analyze_coin(coin)
        await asyncio.sleep(0.5)
        return r
    except Exception as e:
        log.error(f"Scan error {coin}: {e}")
        return None


def _check_heartbeat():
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
            for g in ["A+", "A"]:
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