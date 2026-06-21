import math
import logging
from datetime import datetime, timezone, timedelta
from config import cfg
from data.cache import cache

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

C = {
    "green":       "#34c759",
    "green_dark":  "#248a3d",
    "green_bg":    "rgba(52,199,89,0.10)",
    "red":         "#ff3b30",
    "red_dark":    "#c0392b",
    "red_bg":      "rgba(255,59,48,0.10)",
    "blue":        "#0071e3",
    "blue_dark":   "#0051a8",
    "blue_bg":     "rgba(0,113,227,0.10)",
    "orange":      "#e8820c",
    "orange_bg":   "rgba(255,149,0,0.10)",
    "yellow_dark": "#7d5a00",
    "purple":      "#7d3dbd",
    "muted":       "#6e6e73",
    "text":        "#1d1d1f",
    "text2":       "#3a3a3c",
}


def make_serializable(obj):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_serializable(i) for i in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (int, str, bool)):
        return obj
    return str(obj)


def fmt_price(n) -> str:
    if n is None or n == 0:
        return "--"
    try:
        n = float(n)
        if n >= 1000:  return f"${n:,.2f}"
        if n >= 100:   return f"${n:.2f}"
        if n >= 1:     return f"${n:.4f}"
        if n >= 0.01:  return f"${n:.6f}"
        return f"${n:.8f}"
    except Exception:
        return "--"


def fmt_pnl(n) -> str:
    if n is None:
        return "--"
    try:
        n    = float(n)
        sign = "+" if n >= 0 else ""
        return f"{sign}${abs(n):.4f}"
    except Exception:
        return "--"


def fmt_pct(n) -> str:
    if n is None:
        return "--"
    try:
        n    = float(n)
        sign = "+" if n >= 0 else ""
        return f"{sign}{n:.2f}%"
    except Exception:
        return "--"


def fmt_duration(opened_at) -> str:
    if not opened_at:
        return "--"
    try:
        if isinstance(opened_at, str):
            opened_at = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
        diff       = datetime.now(timezone.utc) - opened_at.replace(tzinfo=timezone.utc)
        total_mins = int(diff.total_seconds() / 60)
        hrs        = total_mins // 60
        mins       = total_mins % 60
        days       = hrs // 24
        if days > 0:  return f"{days}d {hrs % 24}h"
        if hrs > 0:   return f"{hrs}h {mins}m"
        return f"{total_mins}m"
    except Exception:
        return "--"


def get_color(type: str, value) -> str:
    if type == "grade":
        return {
            "A+": C["green"],
            "A":  C["blue"],
            "B":  C["orange"],
            "C":  C["yellow_dark"],
            "F":  C["muted"]
        }.get(str(value), C["muted"])

    if type == "pnl":
        try:
            return C["green_dark"] if float(value) >= 0 else C["red_dark"]
        except Exception:
            return C["muted"]

    if type == "progress":
        try:
            pct = float(value)
            if pct >= 75: return C["green"]
            if pct >= 50: return C["blue"]
            if pct >= 25: return C["orange"]
            return C["red"]
        except Exception:
            return C["muted"]

    if type == "health":
        return {
            "HEALTHY":     C["green_dark"],
            "WARNING":     C["orange"],
            "INVALIDATED": C["red_dark"]
        }.get(str(value), C["muted"])

    if type == "winrate":
        try:
            wr = float(value)
            if wr >= 55: return C["green_dark"]
            if wr >= 45: return C["orange"]
            return C["red_dark"]
        except Exception:
            return C["muted"]

    return C["muted"]


def grade_color(grade: str) -> str:
    return get_color("grade", grade)


def pnl_color(n) -> str:
    return get_color("pnl", n)


def progress_color(pct: float) -> str:
    return get_color("progress", pct)


def health_color(state: str) -> str:
    return get_color("health", state)


def health_emoji(state: str) -> str:
    return {
        "HEALTHY":     "✅",
        "WARNING":     "⚠️",
        "INVALIDATED": "🚨"
    }.get(state, "—")


def build_performance_data(stats: dict) -> dict:
    empty = {
        "win_rate":       "--%",
        "win_rate_color": C["muted"],
        "win_rate_sub":   "0 trades",
        "total_pnl":      "$--",
        "pnl_color":      C["muted"],
        "pnl_sub":        "0W · 0L",
        "profit_factor":  "--",
        "pf_sub":         "$0 / $0",
        "best_trade":     "$--",
        "best_sub":       "--",
        "max_drawdown":   "--%",
        "dd_color":       C["muted"],
        "dd_sub":         "peak: $0",
        "aplus_wr":       "0%",
        "aplus_bar":      0,
        "aplus_detail":   "0W · 0L · 0 trades",
        "a_wr":           "0%",
        "a_bar":          0,
        "a_detail":       "0W · 0L · 0 trades",
        "b_wr":           "0%",
        "b_bar":          0,
        "b_detail":       "0W · 0L · 0 trades · paper only"
    }

    if not stats:
        return empty

    try:
        from database import SessionLocal, Signal as SignalModel
        with SessionLocal() as db:
            closed_signals = db.query(SignalModel).filter(
                SignalModel.outcome.notin_(["pending"]),
                SignalModel.outcome.isnot(None)
            ).order_by(SignalModel.timestamp.asc()).all()
    except Exception as e:
        log.error(f"build_performance_data query failed: {e}")
        return empty

    if not closed_signals:
        return empty

    wr = stats.get("win_rate", 0)
    tp = stats.get("total_pnl", 0)

    gross_p = sum(float(s.pnl or 0) for s in closed_signals if (s.pnl or 0) > 0)
    gross_l = abs(sum(float(s.pnl or 0) for s in closed_signals if (s.pnl or 0) < 0))
    pf      = round(gross_p / gross_l, 2) if gross_l > 0 else 0

    pnls   = [float(s.pnl or 0) for s in closed_signals]
    best   = max(pnls) if pnls else 0
    best_s = next((s for s in closed_signals if float(s.pnl or 0) == best), None)

    peak   = 0
    max_dd = 0
    equity = 0
    for s in closed_signals:
        equity += float(s.pnl or 0)
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    bg    = stats.get("by_grade", {})
    ap    = bg.get("A+", {})
    a     = bg.get("A", {})
    b     = bg.get("B", {})
    ap_wr = ap.get("win_rate", 0)
    a_wr  = a.get("win_rate", 0)
    b_wr  = b.get("win_rate", 0)

    return {
        "win_rate":       f"{wr}%",
        "win_rate_color": get_color("winrate", wr),
        "win_rate_sub":   f"{stats.get('closed', 0)} closed",
        "total_pnl":      fmt_pnl(tp),
        "pnl_color":      pnl_color(tp),
        "pnl_sub":        f"{stats.get('wins',0)}W · {stats.get('losses',0)}L",
        "profit_factor":  str(pf) if pf > 0 else "∞",
        "pf_sub":         f"${gross_p:.2f} / ${gross_l:.2f}",
        "best_trade":     fmt_pnl(best),
        "best_sub":       best_s.coin if best_s else "--",
        "max_drawdown":   f"{max_dd:.1f}%",
        "dd_color":       (
            get_color("health", "HEALTHY")     if max_dd < 10 else
            get_color("health", "WARNING")     if max_dd < 20 else
            get_color("health", "INVALIDATED")
        ),
        "dd_sub":         f"peak: ${peak:.2f}",
        "aplus_wr":       f"{ap_wr}%",
        "aplus_bar":      ap_wr,
        "aplus_detail":   f"{ap.get('wins',0)}W · {(ap.get('total',0) - ap.get('wins',0))}L · {ap.get('total',0)} trades · {fmt_pnl(ap.get('total_pnl',0))}",
        "a_wr":           f"{a_wr}%",
        "a_bar":          a_wr,
        "a_detail":       f"{a.get('wins',0)}W · {(a.get('total',0) - a.get('wins',0))}L · {a.get('total',0)} trades · {fmt_pnl(a.get('total_pnl',0))}",
        "b_wr":           f"{b_wr}%",
        "b_bar":          b_wr,
        "b_detail":       f"{b.get('wins',0)}W · {(b.get('total',0) - b.get('wins',0))}L · {b.get('total',0)} trades · {fmt_pnl(b.get('total_pnl',0))}"
    }


def build_history_data(signals: list) -> list:
    result = []
    for s in signals[:10]:
        pnl     = s.get("pnl") or 0
        outcome = s.get("outcome", "pending")
        is_long = s.get("direction") == "LONG"

        try:
            pnl_float = float(pnl)
        except Exception:
            pnl_float = 0.0

        border_color = (
            C["green"] if outcome == "win" else
            C["red"]   if outcome == "loss" else
            "rgba(0,0,0,0.1)"
        )

        ts_ist = "--"
        try:
            if s.get("timestamp"):
                ts_ist = datetime.fromisoformat(
                    s["timestamp"].replace("Z", "+00:00")
                ).astimezone(IST).strftime("%d %b %I:%M %p IST")
        except Exception:
            pass

        result.append({
            "id":               s.get("id"),
            "coin":             s.get("coin", "--"),
            "direction":        s.get("direction", "--"),
            "dir_emoji":        "📈" if is_long else "📉",
            "dir_color":        C["green_dark"] if is_long else C["red_dark"],
            "grade":            s.get("grade", "--"),
            "outcome":          outcome,
            "outcome_emoji":    "✅" if outcome == "win" else "❌" if outcome == "loss" else "⏹",
            "border_color":     border_color,
            "pnl":              fmt_pnl(pnl_float),
            "pnl_raw":          round(pnl_float, 4),
            "pnl_color":        pnl_color(pnl_float),
            "close_reason":     "--",
            "closed_at":        "--",
            "opened_at":        s.get("timestamp"),
            "entry_price":      s.get("entry"),
            "exit_price":       s.get("exit_price"),
            "sl_price":         s.get("sl"),
            "tp1_price":        s.get("tp1"),
            "tp2_price":        None,
            "risk_amt":         s.get("risk_amt"),
            "position_size":    s.get("position"),
            "leverage":         s.get("leverage"),
            "regime_at_entry":  s.get("regime"),
            "session_at_entry": s.get("session"),
            "score_at_entry":   s.get("score"),
            "ts_ist":           ts_ist,
        })

    return result


def build_radar_data(results: list) -> list:
    radar = []
    for r in results:
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
            "grade_color":    grade_color(grade),
            "direction":      dir_,
            "dir_emoji":      "📈" if dir_ == "LONG" else "📉" if dir_ == "SHORT" else "👁" if dir_ == "WATCH" else "—",
            "dir_color":      C["green_dark"] if dir_ == "LONG" else C["red_dark"] if dir_ == "SHORT" else C["orange"] if dir_ == "WATCH" else C["muted"],
            "score":          score,
            "score_pct":      min(100, score),
            "price":          fmt_price(price),
            "change":         fmt_pct(change),
            "change_color":   pnl_color(change),
            "tradeable":      grade in ["A+", "A"] and dir_ in ["LONG", "SHORT"],
            "confidence":     expl.get("confidence_label", ""),
            "ml_probability": ml_prob,
            "actual_rr":      r.get("actual_rr", 0),
            "tp_mult":        r.get("tp_mult", 2.0),
        })

    return radar


def build_signal_queue(results: list) -> list:
    tradeable = [
        r for r in results
        if r.get("grade") in ["A+", "A"] and
        r.get("direction") in ["LONG", "SHORT"]
    ][:3]

    queue = []
    for r in tradeable:
        sig     = r.get("signal", {})
        grade   = r.get("grade", "?")
        dir_    = r.get("direction", "?")
        is_long = dir_ == "LONG"
        expl    = r.get("explanation", {})

        queue.append({
            "coin":             r.get("coin", "--"),
            "grade":            grade,
            "grade_color":      grade_color(grade),
            "direction":        dir_,
            "dir_emoji":        "📈" if is_long else "📉",
            "dir_color":        C["green_dark"] if is_long else C["red_dark"],
            "score":            r.get("score", 0),
            "entry":            fmt_price(sig.get("entry")),
            "sl":               fmt_price(sig.get("sl")),
            "tp1":              fmt_price(sig.get("tp1")),
            "tp2":              None,
            "risk_amt":         f"${sig.get('risk_amt', 0):.2f}",
            "sl_pct":           f"{sig.get('sl_pct', 0):.2f}%",
            "regime":           r.get("regime", "--"),
            "session":          r.get("session", "--"),
            "thesis":           expl.get("thesis", ""),
            "risk_thesis":      expl.get("risk_thesis", ""),
            "confidence_label": expl.get("confidence_label", ""),
            "no_trade_reason":  expl.get("no_trade_reason", ""),
            "ml_probability":   r.get("ml_probability"),
            "actual_rr":        r.get("actual_rr", 0),
            "tp_mult":          r.get("tp_mult", 2.0),
        })

    return queue


def build_header_data(stats: dict) -> dict:
    today_pnl = 0.0
    try:
        from database import SessionLocal, Signal as SignalModel
        from datetime import date
        with SessionLocal() as db:
            today_str  = date.today().isoformat()
            today_sigs = db.query(SignalModel).filter(
                SignalModel.timestamp >= today_str,
                SignalModel.outcome.notin_(["pending"]),
                SignalModel.outcome.isnot(None)
            ).all()
            today_pnl = sum(float(s.pnl or 0) for s in today_sigs)
    except Exception as e:
        log.error(f"build_header_data today pnl failed: {e}")

    wr = stats.get("win_rate", 0) if stats else 0

    last_scan_time = "--"
    try:
        import runtime_state as rs
        last_ts = rs.get_last_signal_time()
        if last_ts:
            last_scan_time = datetime.fromtimestamp(last_ts, tz=IST).strftime("%I:%M %p IST")
    except Exception:
        pass

    mode = "live" if not cfg.PAPER_TRADING else "paper"

    return {
        "today_pnl":       fmt_pnl(today_pnl),
        "today_pnl_color": pnl_color(today_pnl),
        "win_rate":        f"{wr}%",
        "win_rate_color":  get_color("winrate", wr),
        "coins_count":     len(cfg.COINS),
        "last_scan_time":  last_scan_time,
        "mode":            mode,
        "mode_color":      C["red_dark"] if mode == "live" else C["blue"],
    }