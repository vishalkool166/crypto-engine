import logging
import time
from datetime import datetime, timezone, date
from database import SessionLocal, Signal as SignalModel, CoinConfig
from data.cache import cache
from alerts.scanner import get_db_stats
from scheduler import get_next_scan_epoch
from config import cfg

log = logging.getLogger(__name__)

_cache: dict = {}
_cache_times: dict = {}

TTL = {
    "summary":     10,
    "trades":       5,
    "signals":     30,
    "performance": 30,
    "universe":    30,
    "health":      15,
}


def _is_fresh(key: str) -> bool:
    return (
        key in _cache and
        key in _cache_times and
        time.time() - _cache_times[key] < TTL.get(key, 15)
    )


def _store(key: str, value):
    _cache[key] = value
    _cache_times[key] = time.time()


def _invalidate(key: str):
    _cache.pop(key, None)
    _cache_times.pop(key, None)


def invalidate_all():
    _cache.clear()
    _cache_times.clear()


def get_summary() -> dict:
    key = "summary"
    if _is_fresh(key):
        return _cache[key]

    try:
        stats = get_db_stats()

        today_pnl    = 0.0
        today_trades = 0
        try:
            today_str = date.today().isoformat()
            with SessionLocal() as db:
                today_sigs = db.query(SignalModel).filter(
                    SignalModel.timestamp >= today_str,
                    SignalModel.outcome.notin_(["pending"]),
                    SignalModel.outcome.isnot(None)
                ).all()
                today_pnl    = sum(float(s.pnl or 0) for s in today_sigs)
                today_trades = len(today_sigs)
        except Exception:
            pass

        mode   = "live" if not cfg.PAPER_TRADING else "paper"
        grades = cfg.MIN_GRADE_TO_TRADE

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
            "today_pnl":       _fmt_pnl(today_pnl),
            "today_pnl_raw":   round(today_pnl, 4),
            "today_pnl_color": _pnl_color(today_pnl),
            "today_trades":    today_trades,
            "win_rate":        f"{stats.get('win_rate', 0)}%",
            "win_rate_raw":    stats.get("win_rate", 0),
            "coins_count":     len(cfg.COINS),
            "tradeable_count": tradeable_count,
            "mode":            mode,
            "grades":          grades,
            "grades_str":      ", ".join(grades),
            "next_scan_epoch": get_next_scan_epoch(),
            "total_signals":   stats.get("total", 0),
            "closed_signals":  stats.get("closed", 0),
            "pending_signals": stats.get("pending", 0),
            "timestamp":       datetime.now(timezone.utc).isoformat(),
        }

        _store(key, result)
        return result

    except Exception as e:
        log.error(f"get_summary error: {e}")
        return {}


def get_performance() -> dict:
    key = "performance"
    if _is_fresh(key):
        return _cache[key]

    try:
        stats = get_db_stats()

        with SessionLocal() as db:
            closed_signals = db.query(SignalModel).filter(
                SignalModel.outcome.notin_(["pending"]),
                SignalModel.outcome.isnot(None)
            ).order_by(SignalModel.timestamp.asc()).all()

        if not closed_signals:
            result = _empty_performance()
            _store(key, result)
            return result

        pnls      = [float(s.pnl or 0) for s in closed_signals]
        gross_p   = sum(p for p in pnls if p > 0)
        gross_l   = abs(sum(p for p in pnls if p < 0))
        pf        = round(gross_p / gross_l, 2) if gross_l > 0 else 0
        best      = max(pnls) if pnls else 0
        best_sig  = next((s for s in closed_signals if float(s.pnl or 0) == best), None)

        peak   = 0
        max_dd = 0
        equity = 0
        equity_curve = []
        for s in closed_signals:
            equity += float(s.pnl or 0)
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
            equity_curve.append({
                "date":   s.timestamp.strftime("%Y-%m-%d") if s.timestamp else "",
                "pnl":    round(float(s.pnl or 0), 4),
                "equity": round(equity, 4)
            })

        bg    = stats.get("by_grade", {})
        ap    = bg.get("A+", {})
        a     = bg.get("A", {})
        b     = bg.get("B", {})
        wr    = stats.get("win_rate", 0)
        tp    = stats.get("total_pnl", 0)

        result = {
            "win_rate":         f"{wr}%",
            "win_rate_raw":     wr,
            "win_rate_color":   _wr_color(wr),
            "win_rate_sub":     f"{stats.get('closed', 0)} closed",
            "total_pnl":        _fmt_pnl(tp),
            "total_pnl_raw":    tp,
            "pnl_color":        _pnl_color(tp),
            "pnl_sub":          f"{stats.get('wins', 0)}W · {stats.get('losses', 0)}L",
            "profit_factor":    str(pf) if pf > 0 else "∞",
            "pf_sub":           f"${gross_p:.2f} / ${gross_l:.2f}",
            "best_trade":       _fmt_pnl(best),
            "best_sub":         best_sig.coin if best_sig else "--",
            "max_drawdown":     f"{max_dd:.1f}%",
            "max_drawdown_raw": max_dd,
            "dd_color": (
                "#00d4aa" if max_dd < 10 else
                "#ff9500" if max_dd < 20 else
                "#ff4466"
            ),
            "dd_sub":           f"peak: ${peak:.2f}",
            "aplus_wr":         f"{ap.get('win_rate', 0)}%",
            "aplus_bar":        ap.get("win_rate", 0),
            "aplus_detail":     f"{ap.get('wins', 0)}W · {ap.get('total', 0) - ap.get('wins', 0)}L · {ap.get('total', 0)} trades · {_fmt_pnl(ap.get('total_pnl', 0))}",
            "a_wr":             f"{a.get('win_rate', 0)}%",
            "a_bar":            a.get("win_rate", 0),
            "a_detail":         f"{a.get('wins', 0)}W · {a.get('total', 0) - a.get('wins', 0)}L · {a.get('total', 0)} trades · {_fmt_pnl(a.get('total_pnl', 0))}",
            "b_wr":             f"{b.get('win_rate', 0)}%",
            "b_bar":            b.get("win_rate", 0),
            "b_detail":         f"{b.get('wins', 0)}W · {b.get('total', 0) - b.get('wins', 0)}L · {b.get('total', 0)} trades · {_fmt_pnl(b.get('total_pnl', 0))}",
            "equity_curve":     equity_curve[-200:],
        }

        _store(key, result)
        return result

    except Exception as e:
        log.error(f"get_performance error: {e}")
        return _empty_performance()


def get_signals_data() -> dict:
    key = "signals"
    if _is_fresh(key):
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
            grade   = r.get("grade", "F")
            dir_    = r.get("direction", "--")
            score   = r.get("score", 0)
            market  = r.get("market", {})
            price   = market.get("price", 0)
            change  = market.get("change24", 0)
            expl    = r.get("explanation", {})
            ml_prob = r.get("ml_probability")

            radar.append({
                "coin":           r.get("coin", "--"),
                "grade":          grade,
                "grade_color":    _grade_color(grade),
                "direction":      dir_,
                "score":          score,
                "price":          _fmt_price(price),
                "price_raw":      price,
                "change":         _fmt_pct(change),
                "change_raw":     change,
                "change_color":   _pnl_color(change),
                "tradeable":      grade in ["A+", "A"] and dir_ in ["LONG", "SHORT"],
                "confidence":     expl.get("confidence_label", ""),
                "ml_probability": ml_prob,
                "actual_rr":      r.get("actual_rr", 0),
                "regime":         r.get("regime", "--"),
                "session":        r.get("session", "--"),
                "funding":        round(market.get("funding", 0) * 100, 4),
            })

        queue = []
        tradeable = [r for r in cached_results if r.get("grade") in cfg.MIN_GRADE_TO_TRADE and r.get("direction") in ["LONG", "SHORT"]]
        for r in tradeable[:5]:
            sig   = r.get("signal", {})
            grade = r.get("grade", "?")
            dir_  = r.get("direction", "?")
            expl  = r.get("explanation", {})

            queue.append({
                "coin":             r.get("coin", "--"),
                "grade":            grade,
                "grade_color":      _grade_color(grade),
                "direction":        dir_,
                "score":            r.get("score", 0),
                "entry":            _fmt_price(sig.get("entry")),
                "entry_raw":        sig.get("entry"),
                "sl":               _fmt_price(sig.get("sl")),
                "sl_raw":           sig.get("sl"),
                "tp1":              _fmt_price(sig.get("tp1")),
                "tp1_raw":          sig.get("tp1"),
                "risk_amt":         f"${sig.get('risk_amt', 0):.2f}",
                "sl_pct":           f"{sig.get('sl_pct', 0):.2f}%",
                "regime":           r.get("regime", "--"),
                "session":          r.get("session", "--"),
                "thesis":           expl.get("thesis", ""),
                "confidence_label": expl.get("confidence_label", ""),
                "ml_probability":   r.get("ml_probability"),
                "actual_rr":        r.get("actual_rr", 0),
                "stake":            sig.get("stake", 0),
                "leverage":         sig.get("leverage", 10),
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
            signals = db.query(SignalModel).filter(
                SignalModel.outcome.notin_(["pending"]),
                SignalModel.outcome.isnot(None)
            ).order_by(SignalModel.timestamp.desc()).limit(limit).all()

        result = []
        for s in signals:
            pnl = float(s.pnl or 0)
            result.append({
                "id":          s.id,
                "coin":        s.coin,
                "direction":   s.direction,
                "grade":       s.grade,
                "grade_color": _grade_color(s.grade),
                "outcome":     s.outcome,
                "pnl":         _fmt_pnl(pnl),
                "pnl_raw":     round(pnl, 4),
                "pnl_color":   _pnl_color(pnl),
                "entry_price": s.entry,
                "exit_price":  s.exit_price,
                "sl_price":    s.sl,
                "tp1_price":   s.tp1,
                "risk_amt":    s.risk_amt,
                "score":       s.score,
                "regime":      s.regime,
                "session":     s.session,
                "timestamp":   s.timestamp.isoformat() if s.timestamp else None,
            })
        return result

    except Exception as e:
        log.error(f"get_history error: {e}")
        return []


def get_universe() -> list:
    key = "universe"
    if _is_fresh(key):
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
            grade  = c.get("grade", "--")     if c else "--"
            score  = c.get("score", 0)        if c else 0
            dir_   = c.get("direction", "--") if c else "--"
            market = c.get("market", {})      if c else {}
            change = market.get("change24", 0)

            result.append({
                "coin":         r.coin,
                "enabled":      r.enabled,
                "tier":         r.tier,
                "source":       r.source,
                "volume_24h":   r.volume_24h,
                "added_at":     r.added_at.isoformat() if r.added_at else None,
                "grade":        grade,
                "grade_color":  _grade_color(grade),
                "score":        score,
                "direction":    dir_,
                "has_signal":   c is not None,
                "price":        _fmt_price(market.get("price", 0)),
                "price_raw":    market.get("price", 0),
                "change":       _fmt_pct(change),
                "change_raw":   change,
                "change_color": _pnl_color(change),
                "funding":      round(market.get("funding", 0) * 100, 4) if market else 0,
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
            change = market.get("change24", 0)
            if not price:
                continue
            result.append({
                "coin":         coin,
                "price":        _fmt_price(price),
                "change":       _fmt_pct(change),
                "change_raw":   change,
                "change_color": _pnl_color(change),
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

        market  = c.get("market", {})
        signal  = c.get("signal", {})
        expl    = c.get("explanation", {})
        wconf   = c.get("wconf", {})
        factors = wconf.get("factors", [])

        factor_list = []
        for f in factors:
            earned = f.get("earned", 0)
            max_w  = f.get("max", f.get("weight", 1))
            pct    = round(earned / max_w * 100) if max_w > 0 else 0
            factor_list.append({
                "key":     f.get("key", ""),
                "label":   f.get("key", "").replace("_", " ").title(),
                "earned":  earned,
                "max":     max_w,
                "pct":     pct,
                "color":   "#00e5b8" if pct >= 70 else "#3d8bff" if pct >= 40 else "#ff9500" if pct > 0 else "#1e1e30",
            })

        factor_list.sort(key=lambda x: x["earned"], reverse=True)

        return {
            "coin":           coin,
            "grade":          c.get("grade", "--"),
            "score":          c.get("score", 0),
            "direction":      c.get("direction", "--"),
            "regime":         c.get("regime", "--"),
            "session":        c.get("session", "--"),
            "ml_probability": c.get("ml_probability"),
            "actual_rr":      c.get("actual_rr", 0),
            "market": {
                "price":       _fmt_price(market.get("price", 0)),
                "change":      _fmt_pct(market.get("change24", 0)),
                "change_color":_pnl_color(market.get("change24", 0)),
                "funding":     round(market.get("funding", 0) * 100, 4),
                "oi_change":   round(market.get("oi_change", 0), 2),
                "long_ratio":  round(market.get("long_ratio", 50), 1),
                "short_ratio": round(market.get("short_ratio", 50), 1),
            },
            "signal": {
                "entry":    _fmt_price(signal.get("entry")),
                "sl":       _fmt_price(signal.get("sl")),
                "tp1":      _fmt_price(signal.get("tp1")),
                "sl_pct":   f"{signal.get('sl_pct', 0):.2f}%",
                "risk_amt": f"${signal.get('risk_amt', 0):.2f}",
                "leverage": signal.get("leverage", 10),
                "stake":    signal.get("stake", 0),
            },
            "thesis":         expl.get("thesis", ""),
            "confidence":     expl.get("confidence_label", ""),
            "factors":        factor_list,
            "norm_score":     wconf.get("norm_score", 0),
            "market_score":   wconf.get("market_score", 0),
            "entry_score":    wconf.get("entry_score", 0),
            "btc_score":      wconf.get("btc_score", 0),
        }

    except Exception as e:
        log.error(f"get_coin_detail error {coin}: {e}")
        return {}


def _empty_performance() -> dict:
    return {
        "win_rate":         "--%",
        "win_rate_raw":     0,
        "win_rate_color":   "#6e6e99",
        "win_rate_sub":     "0 trades",
        "total_pnl":        "--",
        "total_pnl_raw":    0,
        "pnl_color":        "#6e6e99",
        "pnl_sub":          "0W · 0L",
        "profit_factor":    "--",
        "pf_sub":           "$0 / $0",
        "best_trade":       "--",
        "best_sub":         "--",
        "max_drawdown":     "--%",
        "max_drawdown_raw": 0,
        "dd_color":         "#6e6e99",
        "dd_sub":           "peak: $0",
        "aplus_wr":         "0%",
        "aplus_bar":        0,
        "aplus_detail":     "0W · 0L · 0 trades",
        "a_wr":             "0%",
        "a_bar":            0,
        "a_detail":         "0W · 0L · 0 trades",
        "b_wr":             "0%",
        "b_bar":            0,
        "b_detail":         "0W · 0L · 0 trades",
        "equity_curve":     [],
    }


def _fmt_price(n) -> str:
    if n is None or n == 0:
        return "--"
    try:
        n = float(n)
        if n >= 10000: return f"${n:,.2f}"
        if n >= 1000:  return f"${n:.2f}"
        if n >= 100:   return f"${n:.3f}"
        if n >= 1:     return f"${n:.4f}"
        if n >= 0.1:   return f"${n:.5f}"
        if n >= 0.01:  return f"${n:.6f}"
        if n >= 0.001: return f"${n:.7f}"
        return f"${n:.8f}"
    except Exception:
        return "--"


def _fmt_pnl(n) -> str:
    if n is None:
        return "--"
    try:
        n    = float(n)
        sign = "+" if n >= 0 else "-"
        return f"{sign}${abs(n):.4f}"
    except Exception:
        return "--"


def _fmt_pct(n) -> str:
    if n is None:
        return "--"
    try:
        n    = float(n)
        sign = "+" if n >= 0 else ""
        return f"{sign}{n:.2f}%"
    except Exception:
        return "--"


def _pnl_color(n) -> str:
    try:
        return "#00d4aa" if float(n) >= 0 else "#ff4466"
    except Exception:
        return "#6e6e99"


def _wr_color(wr) -> str:
    try:
        wr = float(wr)
        if wr >= 55: return "#00d4aa"
        if wr >= 40: return "#ff9500"
        return "#ff4466"
    except Exception:
        return "#6e6e99"


def _grade_color(grade: str) -> str:
    return {
        "A+": "#aa66ff",
        "A":  "#4488ff",
        "B":  "#ff9500",
        "C":  "#ffcc00",
        "F":  "#6e6e99",
    }.get(str(grade), "#6e6e99")