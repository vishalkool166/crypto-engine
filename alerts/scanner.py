import asyncio
import logging
from config import cfg
from data.fetcher import get_all_data
from data.cache import cache
from database import SessionLocal, Signal as SignalModel
from engines.indicators import calculate_all
from engines.regime import detect_regime
from engines.sweep import detect_sweep
from engines.displacement import detect_displacement
from engines.retest import detect_retest
from engines.confluence import score_confluence
from engines.signal import (
    get_tier, get_session,
    run_no_trade_engine, generate_signal
)
from alerts.telegram import send_signal, send_scan_summary
from trade.state import state_manager
from trade.manager import trade_manager

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════
def _interpret_oi(market: dict) -> dict:
    fund = market["funding"] * 100
    pu   = market["change24"] > 0
    oiu  = market["oi_change"] > 1

    # ── FIXED OI LOGIC ──
    # price up   + OI up   = longs added   = bullish confirm
    # price down + OI up   = shorts added  = bearish confirm
    # price up   + OI down = long squeeze  = bullish exhaustion
    # price down + OI down = short squeeze = bearish exhaustion

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
        "pdh": float(d1d_df.iloc[-2]["high"])
               if len(d1d_df) >= 2 else 0,
        "pdl": float(d1d_df.iloc[-2]["low"])
               if len(d1d_df) >= 2 else 0,
        "pdc": float(d1d_df.iloc[-2]["close"])
               if len(d1d_df) >= 2 else 0,
        "pwh": float(d1w_df.iloc[-2]["high"])
               if len(d1w_df) >= 2 else 0,
        "pwl": float(d1w_df.iloc[-2]["low"])
               if len(d1w_df) >= 2 else 0,
    }


def _btc_instability(btc_data: dict) -> dict:
    warnings = []
    adx = btc_data.get("adx")
    if adx and adx < 18:
        warnings.append("⚠️ BTC ADX weak — ranging")
    if (
        btc_data.get("structure", {}).get(
            "struct_bias"
        ) == "bear" and
        btc_data.get("trend", {}).get(
            "cls"
        ) == "bull"
    ):
        warnings.append("⚠️ BTC CHoCH detected")
    return {
        "stable":   len(warnings) == 0,
        "warnings": warnings,
        "score":    max(0, 8 - len(warnings) * 3)
    }


# ═══════════════════════════════════════════════════════
# SAVE SIGNAL TO DB
# ═══════════════════════════════════════════════════════
def save_signal_to_db(
    signal:  dict,
    coin:    str,
    regime:  str,
    session: str,
    sweep:   dict,
    retest:  dict,
    disp:    dict,
    market:  dict
) -> int:

    if signal.get("grade") not in ["A+", "A"]:
        return None

    if signal.get("direction") in [
        "NO TRADE", "WATCH", "SKIP"
    ]:
        return None

    try:
        db  = SessionLocal()
        row = SignalModel(
            coin         = coin,
            direction    = signal["direction"],
            grade        = signal["grade"],
            score        = signal["score"],
            signal_type  = signal["signal_type"],
            entry        = signal.get("entry", 0),
            sl           = signal.get("sl", 0),
            tp1          = signal.get("tp1", 0),
            tp2          = signal.get("tp2", 0),
            tp3          = signal.get("tp2", 0),
            sl_pct       = signal.get("sl_pct", 0),
            risk_amt     = signal.get("risk_amt", 0),
            risk_pct     = signal.get("risk_pct", 0),
            position     = signal.get("pos_size", 0),
            leverage     = str(cfg.LEVERAGE) + "x",
            regime       = regime,
            session      = session,
            sweep_score  = sweep.get("score", 0),
            retest_score = retest.get("score", 0),
            disp_score   = disp.get("score", 0),
            funding      = market.get("funding", 0),
            oi_signal    = _interpret_oi(market).get(
                "primary_label", ""
            ),
            outcome      = "pending"
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        log.info(
            f"Signal saved — ID:{row.id} "
            f"{coin} Grade:{signal['grade']}"
        )
        return row.id

    except Exception as e:
        log.error(f"DB save error: {e}")
        return None

    finally:
        db.close()


# ═══════════════════════════════════════════════════════
# ATTEMPT TRADE
# ═══════════════════════════════════════════════════════
async def _attempt_trade(
    signal: dict,
    coin:   str
):
    if (
        signal.get("grade") in cfg.MIN_GRADE_TO_TRADE
        and
        signal.get("direction") in ["LONG", "SHORT"]
        and
        state_manager.is_idle
    ):
        log.info(
            f"Grade {signal['grade']} — "
            f"attempting trade: {coin}"
        )
        await trade_manager.open_trade(
            signal    = signal,
            signal_id = signal.get("db_id")
        )
        return True

    elif signal.get("grade") in ["A+", "A"]:
        log.info(
            f"Signal alert only — "
            f"not executing: {coin} "
            f"idle:{state_manager.is_idle}"
        )
        return False

    return False


# ═══════════════════════════════════════════════════════
# ANALYZE COIN
# ═══════════════════════════════════════════════════════
async def analyze_coin(
    coin:     str,
    capital:  float = cfg.CAPITAL,
    leverage: int   = cfg.LEVERAGE
) -> dict:

    # ── CHECK CACHE ──
    # TTL matches scanner interval — 15 minutes
    cached = cache.get(f"signal_{coin}")
    if cached:
        log.debug(f"Cache hit: {coin}")
        signal = cached.get("signal", {})
        await _attempt_trade(signal, coin)
        return cached

    # ── FETCH ALL DATA ──
    try:
        raw = await get_all_data(coin)
    except Exception as e:
        log.error(f"Data fetch failed {coin}: {e}")
        return {"coin": coin, "error": str(e)}

    klines      = raw["klines"]
    news_filter = raw["news_filter"]

    # ── GET 15M DATA ──
    df_15m = raw.get("klines_15m")

    # Calculate indicators
    d1w = calculate_all(klines["1w"])
    d1d = calculate_all(klines["1d"])
    d4h = calculate_all(klines["4h"])
    d1h = calculate_all(klines["1h"])

    # ── BTC DATA ──
    btc_data = None
    if coin == "BTC":
        btc_data = d1d
    else:
        btc_cached = cache.get("btc_1d_data")
        if btc_cached:
            btc_data = btc_cached
            log.debug("BTC data from cache")
        else:
            try:
                btc_raw  = await get_all_data("BTC")
                btc_data = calculate_all(
                    btc_raw["klines"]["1d"]
                )
                cache.set(
                    "btc_1d_data",
                    btc_data,
                    ttl=900
                )
                log.debug(
                    "BTC data fetched and cached"
                )
            except Exception:
                btc_data = None
                log.warning("BTC data fetch failed")

    btc_inst = (
        _btc_instability(btc_data)
        if btc_data
        else {
            "stable":   False,
            "warnings": ["BTC data unavailable now"],
            "score":    0
        }
    )

    # Market dict
    market = {
        "price":       raw["price"],
        "change24":    raw["change24"],
        "high24":      raw["high24"],
        "low24":       raw["low24"],
        "vol24":       raw["vol24"],
        "funding":     raw["funding"],
        "oi":          raw["oi"],
        "oi_change":   raw["oi_change"],
        "long_ratio":  raw["long_ratio"],
        "short_ratio": raw["short_ratio"],
        "fear_greed":  {
            "value": 50,
            "label": "Neutral"
        }
    }

    # Run engines
    key_levels = _extract_key_levels(
        klines["1d"], klines["1w"]
    )
    session   = get_session()
    regime    = detect_regime(d1d, d4h)
    sweep     = detect_sweep(
        klines["1d"], key_levels,
        d1d.get("atr", 0),
        d1d["swings"]
    )
    disp      = detect_displacement(
        klines["4h"],
        d4h.get("atr", 0)
    )
    retest    = detect_retest(
        klines["4h"], d4h, sweep, disp
    )
    oi_matrix = _interpret_oi(market)

    # Score confluence
    wconf = score_confluence(
        d1w, d1d, d4h, d1h,
        market, key_levels,
        session, btc_data,
        btc_inst, regime,
        sweep, disp,
        retest, oi_matrix,
        coin
    )

    # No trade engine
    no_trade = run_no_trade_engine(
        regime, d1d, d4h,
        market, session,
        sweep, disp,
        retest, btc_data,
        btc_inst, oi_matrix,
        news_filter,
        wconf["norm_score"]
    )

    # ── GENERATE SIGNAL WITH 15M ──
    signal = generate_signal(
        d1d, d4h,
        wconf, no_trade,
        market, key_levels,
        capital, leverage,
        df_15m = df_15m
    )

    # Attach extra fields
    signal["sweep_score"] = sweep.get("score", 0)
    signal["disp_score"]  = disp.get("score", 0)
    signal["funding"]     = raw["funding"]
    signal["coin"]        = coin

    # Save to DB
    db_id = save_signal_to_db(
        signal  = signal,
        coin    = coin,
        regime  = regime["label"],
        session = session["name"],
        sweep   = sweep,
        retest  = retest,
        disp    = disp,
        market  = market
    )

    if db_id:
        signal["db_id"] = db_id

    # Build result
    result = {
        "coin":         coin,
        "grade":        signal["grade"],
        "score":        signal["score"],
        "direction":    signal["direction"],
        "signal":       signal,
        "market":       market,
        "regime":       regime["label"],
        "session":      session["name"],
        "d1d":          d1d,
        "d4h":          d4h,
        "d1h":          d1h,
        "d1w":          d1w,
        "key_levels":   key_levels,
        "sweep":        sweep,
        "retest":       retest,
        "displacement": disp,
        "wconf":        wconf,
        "no_trade":     no_trade,
        "news_filter":  news_filter
    }

    # ── CACHE 15 MINUTES — matches scan interval ──
    cache.set(f"signal_{coin}", result, ttl=900)

    # ── ATTEMPT TRADE ──
    traded = await _attempt_trade(signal, coin)

    # ── SEND ALERT IF NOT TRADED ──
    if (
        not traded and
        signal.get("grade") in ["A+", "A"]
    ):
        await send_signal(
            signal,
            coin,
            regime["label"],
            session["name"]
        )

    return result


# ═══════════════════════════════════════════════════════
# SCAN ALL COINS
# ═══════════════════════════════════════════════════════
async def scan_all_coins() -> list:
    results = []

    if not state_manager.is_idle:
        trade = state_manager.current_trade
        log.info(
            f"Scan — active trade: "
            f"{trade.coin} {trade.direction} "
            f"{trade.state}"
        )
    else:
        log.info(
            "Scan — bot idle, looking for signals"
        )

    # ── TIER 1 ──
    log.info(f"Scanning Tier 1: {cfg.TIER1}")
    for coin in cfg.TIER1:
        try:
            r = await analyze_coin(coin)
            if "error" not in r:
                results.append(r)

            if not state_manager.is_idle:
                log.info(
                    f"Trade opened on {coin} — "
                    f"continuing scan for alerts only"
                )

            await asyncio.sleep(0.5)

        except Exception as e:
            log.error(f"Scan error {coin}: {e}")
            continue

    # ── TIER 2 ──
    log.info(f"Scanning Tier 2: {cfg.TIER2}")
    for coin in cfg.TIER2:
        try:
            r = await analyze_coin(coin)
            if "error" not in r:
                results.append(r)
            await asyncio.sleep(0.5)

        except Exception as e:
            log.error(f"Scan error {coin}: {e}")
            continue

    # Sort by score
    results.sort(
        key=lambda x: x.get("score", 0),
        reverse=True
    )

    # Send summary
    await send_scan_summary(results)

    log.info(
        f"Scan complete — "
        f"{len(results)} coins analyzed"
    )

    return results


# ═══════════════════════════════════════════════════════
# GET DB STATS
# ═══════════════════════════════════════════════════════
def get_db_stats() -> dict:
    try:
        db       = SessionLocal()
        all_sigs = db.query(SignalModel).all()
        closed   = [
            s for s in all_sigs
            if s.outcome not in ["pending", None]
        ]
        wins = [
            s for s in closed
            if s.outcome == "win"
        ]

        by_grade = {}
        for g in ["A+", "A"]:
            g_trades = [
                s for s in closed
                if s.grade == g
            ]
            g_wins = [
                s for s in g_trades
                if s.outcome == "win"
            ]
            by_grade[g] = {
                "total":    len(g_trades),
                "wins":     len(g_wins),
                "losses":   len(g_trades) - len(g_wins),
                "win_rate": round(
                    len(g_wins) /
                    len(g_trades) * 100, 1
                ) if g_trades else 0,
                "total_pnl": round(
                    sum(
                        s.pnl or 0
                        for s in g_trades
                    ), 2
                )
            }

        return {
            "total":     len(all_sigs),
            "closed":    len(closed),
            "pending":   len(all_sigs) - len(closed),
            "wins":      len(wins),
            "losses":    len(closed) - len(wins),
            "win_rate":  round(
                len(wins) /
                len(closed) * 100, 1
            ) if closed else 0,
            "total_pnl": round(
                sum(s.pnl or 0 for s in closed), 2
            ),
            "by_grade":  by_grade
        }

    except Exception as e:
        log.error(f"Stats error: {e}")
        return {}

    finally:
        db.close()