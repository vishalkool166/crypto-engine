import logging
import time
from datetime import datetime, timezone, date
from database import SessionLocal, Signal as SignalModel, Trade as TradeModel, CoinConfig
from data.cache import cache
from alerts.scanner import get_db_stats
from scheduler import get_next_scan_epoch
from config import cfg

log = logging.getLogger(__name__)

_cache:      dict = {}
_cache_times:dict = {}

TTL = {
    "summary":     10,
    "signals":     30,
    "performance": 60,
    "universe":    30,
    "history":     15,
}


def _fresh(key: str) -> bool:
    return (
        key in _cache and
        key in _cache_times and
        time.time() - _cache_times[key] < TTL.get(key, 15)
    )


def _store(key: str, value):
    _cache[key]       = value
    _cache_times[key] = time.time()


def invalidate_all():
    _cache.clear()
    _cache_times.clear()


def _invalidate(key: str):
    _cache.pop(key, None)
    _cache_times.pop(key, None)


def get_summary() -> dict:
    key = "summary"
    if _fresh(key):
        return _cache[key]

    try:
        stats = get_db_stats()

        today_pnl    = 0.0
        today_trades = 0
        try:
            today_start = datetime(date.today().year, date.today().month, date.today().day, tzinfo=timezone.utc)
            with SessionLocal() as db:
                today_closed = db.query(TradeModel).filter(
                    TradeModel.closed_at >= today_start,
                    TradeModel.outcome.in_(["win", "loss"])
                ).all()
                today_pnl    = sum(float(t.net_pnl or t.pnl or 0) for t in today_closed)
                today_trades = len(today_closed)
        except Exception:
            pass

        cached_results = []
        for coin in cfg.COINS:
            c = cache.get_raw(f"signal_{coin}")
            if c:
                cached_results.append(c)

        tradeable_count = len([
            r for r in cached_results
            if r.get("grade") in cfg.MIN_GRADE_TO_TRADE
            and r.get("direction") in ["LONG", "SHORT"]
        ])

        result = {
            "today_pnl":        round(today_pnl, 4),
            "today_pnl_pos":    today_pnl >= 0,
            "today_trades":     today_trades,
            "win_rate":         stats.get("win_rate", 0),
            "coins_count":      len(cfg.COINS),
            "tradeable_count":  tradeable_count,
            "mode":             "live" if not cfg.PAPER_TRADING else "paper",
            "grades":           cfg.MIN_GRADE_TO_TRADE,
            "next_scan_epoch":  get_next_scan_epoch(),
            "total_signals":    stats.get("total",   0),
            "closed_signals":   stats.get("closed",  0),
            "pending_signals":  stats.get("pending", 0),
            "wins":             stats.get("wins",    0),
            "losses":           stats.get("losses",  0),
            "total_pnl":        stats.get("total_pnl", 0),
            "timestamp":        datetime.now(timezone.utc).isoformat(),
        }

        _store(key, result)
        return result

    except Exception as e:
        log.error(f"get_summary error: {e}")
        return {}


def get_performance() -> dict:
    key = "performance"
    if _fresh(key):
        return _cache[key]

    try:
        with SessionLocal() as db:
            closed_trades = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).order_by(TradeModel.opened_at.asc()).all()

        if not closed_trades:
            result = _empty_performance()
            _store(key, result)
            return result

        pnls     = [float(t.net_pnl or t.pnl or 0) for t in closed_trades]
        wins     = [t for t in closed_trades if t.outcome == "win"]
        losses   = [t for t in closed_trades if t.outcome == "loss"]
        win_rate = round(len(wins) / len(closed_trades) * 100, 1) if closed_trades else 0

        gross_p  = sum(p for p in pnls if p > 0)
        gross_l  = abs(sum(p for p in pnls if p < 0))
        pf       = round(gross_p / gross_l, 2) if gross_l > 0 else 0
        best     = max(pnls) if pnls else 0
        best_t   = next((t for t in closed_trades if float(t.net_pnl or t.pnl or 0) == best), None)
        total_pnl= round(sum(pnls), 4)

        peak         = 0
        max_dd       = 0
        equity       = 0
        equity_curve = []

        for t in closed_trades:
            equity += float(t.net_pnl or t.pnl or 0)
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
            equity_curve.append({
                "date":   t.opened_at.strftime("%Y-%m-%d") if t.opened_at else "",
                "pnl":    round(float(t.net_pnl or t.pnl or 0), 4),
                "equity": round(equity, 4)
            })

        def _grade_stats(grade: str) -> dict:
            gt = [t for t in closed_trades if t.grade == grade]
            gw = [t for t in gt if t.outcome == "win"]
            return {
                "win_rate": round(len(gw) / len(gt) * 100, 1) if gt else 0,
                "wins":     len(gw),
                "total":    len(gt),
                "pnl":      round(sum(float(t.net_pnl or t.pnl or 0) for t in gt), 4),
            }

        result = {
            "win_rate":         win_rate,
            "total_pnl":        total_pnl,
            "total_pnl_pos":    total_pnl >= 0,
            "wins":             len(wins),
            "losses":           len(losses),
            "closed":           len(closed_trades),
            "profit_factor":    pf,
            "gross_profit":     round(gross_p, 2),
            "gross_loss":       round(gross_l, 2),
            "best_trade":       round(best, 4),
            "best_trade_coin":  best_t.coin if best_t else "--",
            "max_drawdown":     round(max_dd, 2),
            "peak_equity":      round(peak, 4),
            "equity_curve":     equity_curve[-200:],
            "aplus": _grade_stats("A+"),
            "a":     _grade_stats("A"),
            "b":     _grade_stats("B"),
        }

        _store(key, result)
        return result

    except Exception as e:
        log.error(f"get_performance error: {e}")
        return _empty_performance()


def get_signals_data() -> dict:
    key = "signals"
    if _fresh(key):
        return _cache[key]

    try:
        cached_results = []
        for coin in cfg.COINS:
            c = cache.get_raw(f"signal_{coin}")
            if c:
                cached_results.append(c)

        cached_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        radar = []
        for r in cached_results:
            market = r.get("market", {})
            sig    = r.get("signal", {})
            expl   = r.get("explanation", {})

            radar.append({
                "coin":           r.get("coin",      "--"),
                "grade":          r.get("grade",     "F"),
                "direction":      r.get("direction", "--"),
                "score":          r.get("score",     0),
                "price":          market.get("price",    0),
                "change":         market.get("change24", 0),
                "funding":        round(market.get("funding", 0) * 100, 4),
                "tradeable":      r.get("grade") in ["A+", "A"] and r.get("direction") in ["LONG", "SHORT"],
                "confidence":     expl.get("confidence_label", ""),
                "ml_probability": r.get("ml_probability"),
                "actual_rr":      r.get("actual_rr", 0),
                "regime":         r.get("regime",  "--"),
                "session":        r.get("session", "--"),
                "timestamp":      r.get("cached_at"),
            })

        queue = []
        tradeable = [
            r for r in cached_results
            if r.get("grade") in cfg.MIN_GRADE_TO_TRADE
            and r.get("direction") in ["LONG", "SHORT"]
        ]

        for r in tradeable[:5]:
            sig  = r.get("signal", {})
            expl = r.get("explanation", {})
            queue.append({
                "coin":             r.get("coin",      "--"),
                "grade":            r.get("grade",     "?"),
                "direction":        r.get("direction", "?"),
                "score":            r.get("score",     0),
                "entry":            sig.get("entry"),
                "sl":               sig.get("sl"),
                "tp1":              sig.get("tp1"),
                "sl_pct":           sig.get("sl_pct",    0),
                "risk_amt":         sig.get("risk_amt",  0),
                "stake":            sig.get("stake",     0),
                "leverage":         sig.get("leverage",  10),
                "regime":           r.get("regime",  "--"),
                "session":          r.get("session", "--"),
                "thesis":           expl.get("thesis", ""),
                "confidence_label": expl.get("confidence_label", ""),
                "ml_probability":   r.get("ml_probability"),
                "actual_rr":        r.get("actual_rr", 0),
            })

        result = {
            "radar":     radar,
            "queue":     queue,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        _store(key, result)
        return result

    except Exception as e:
        log.error(f"get_signals_data error: {e}")
        return {"radar": [], "queue": []}


def get_history(limit: int = 10) -> list:
    try:
        with SessionLocal() as db:
            trades = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).order_by(TradeModel.opened_at.desc()).limit(limit).all()

        return [{
            "id":          t.id,
            "coin":        t.coin,
            "direction":   t.direction,
            "grade":       t.grade,
            "outcome":     t.outcome,
            "pnl":         round(float(t.net_pnl or t.pnl or 0), 4),
            "pnl_pos":     (t.net_pnl or t.pnl or 0) >= 0,
            "entry_price": t.entry_price,
            "exit_price":  t.exit_price,
            "sl_price":    t.sl_price,
            "tp1_price":   t.tp1_price,
            "risk_amt":    t.margin_used,
            "score":       t.score_at_entry,
            "regime":      t.regime_at_entry,
            "session":     t.session_at_entry,
            "timestamp":   t.opened_at.replace(tzinfo=timezone.utc).isoformat() if t.opened_at else None,
        } for t in trades]

    except Exception as e:
        log.error(f"get_history error: {e}")
        return []


def get_universe() -> list:
    key = "universe"
    if _fresh(key):
        return _cache[key]

    try:
        with SessionLocal() as db:
            rows = db.query(CoinConfig).order_by(
                CoinConfig.enabled.desc(),
                CoinConfig.coin.asc()
            ).all()

        result = []
        for r in rows:
            c      = cache.get_raw(f"signal_{r.coin}")
            market = c.get("market", {}) if c else {}

            result.append({
                "coin":       r.coin,
                "enabled":    r.enabled,
                "tier":       r.tier,
                "source":     r.source,
                "volume_24h": r.volume_24h,
                "added_at":   r.added_at.isoformat() if r.added_at else None,
                "grade":      c.get("grade",     "--") if c else "--",
                "score":      c.get("score",     0)    if c else 0,
                "direction":  c.get("direction", "--") if c else "--",
                "has_signal": c is not None,
                "price":      market.get("price",    0),
                "change":     market.get("change24", 0),
                "funding":    round(market.get("funding", 0) * 100, 4) if market else 0,
            })

        _store(key, result)
        return result

    except Exception as e:
        log.error(f"get_universe error: {e}")
        return []


def get_ticker_bar() -> list:
    try:
        result = []
        for coin in cfg.COINS[:20]:
            c = cache.get_raw(f"signal_{coin}")
            if not c:
                continue
            market = c.get("market", {})
            price  = market.get("price", 0)
            if not price:
                continue
            result.append({
                "coin":   coin,
                "price":  price,
                "change": market.get("change24", 0),
            })
        return result
    except Exception as e:
        log.error(f"get_ticker_bar error: {e}")
        return []


def get_coin_detail(coin: str) -> dict:
    try:
        c = cache.get_raw(f"signal_{coin}")
        if not c:
            return {}

        market  = c.get("market",      {})
        signal  = c.get("signal",      {})
        expl    = c.get("explanation", {})
        wconf   = c.get("wconf",       {})
        factors = wconf.get("factors", [])

        factor_list = []
        for f in factors:
            earned = f.get("earned", 0)
            max_w  = f.get("max", f.get("weight", 1))
            pct    = round(earned / max_w * 100) if max_w > 0 else 0
            factor_list.append({
                "key":    f.get("key", ""),
                "label":  f.get("key", "").replace("_", " ").title(),
                "earned": earned,
                "max":    max_w,
                "pct":    pct,
            })

        factor_list.sort(key=lambda x: x["earned"], reverse=True)

        return {
            "coin":           coin,
            "grade":          c.get("grade",     "--"),
            "score":          c.get("score",     0),
            "direction":      c.get("direction", "--"),
            "regime":         c.get("regime",    "--"),
            "session":        c.get("session",   "--"),
            "ml_probability": c.get("ml_probability"),
            "actual_rr":      c.get("actual_rr", 0),
            "market": {
                "price":       market.get("price",    0),
                "change":      market.get("change24", 0),
                "change_pos":  market.get("change24", 0) >= 0,
                "funding":     round(market.get("funding",   0) * 100, 4),
                "oi_change":   round(market.get("oi_change", 0), 2),
                "long_ratio":  round(market.get("long_ratio",  50), 1),
                "short_ratio": round(market.get("short_ratio", 50), 1),
            },
            "signal": {
                "entry":    signal.get("entry"),
                "sl":       signal.get("sl"),
                "tp1":      signal.get("tp1"),
                "sl_pct":   signal.get("sl_pct",   0),
                "risk_amt": signal.get("risk_amt",  0),
                "leverage": signal.get("leverage",  10),
                "stake":    signal.get("stake",     0),
            },
            "thesis":       expl.get("thesis", ""),
            "confidence":   expl.get("confidence_label", ""),
            "factors":      factor_list,
            "norm_score":   wconf.get("norm_score",   0),
            "market_score": wconf.get("market_score", 0),
            "entry_score":  wconf.get("entry_score",  0),
            "btc_score":    wconf.get("btc_score",    0),
        }

    except Exception as e:
        log.error(f"get_coin_detail error {coin}: {e}")
        return {}


def _empty_performance() -> dict:
    return {
        "win_rate":        0,
        "total_pnl":       0,
        "total_pnl_pos":   True,
        "wins":            0,
        "losses":          0,
        "closed":          0,
        "profit_factor":   0,
        "gross_profit":    0,
        "gross_loss":      0,
        "best_trade":      0,
        "best_trade_coin": "--",
        "max_drawdown":    0,
        "peak_equity":     0,
        "equity_curve":    [],
        "aplus": {"win_rate": 0, "wins": 0, "total": 0, "pnl": 0},
        "a":     {"win_rate": 0, "wins": 0, "total": 0, "pnl": 0},
        "b":     {"win_rate": 0, "wins": 0, "total": 0, "pnl": 0},
    }