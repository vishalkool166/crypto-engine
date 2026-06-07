from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from backtest.factor_analysis import run_factor_analysis
from datetime import datetime, timezone
from database import (
    get_db, Signal as SignalModel,
    Trade as TradeModel, BacktestResult
)
from alerts.scanner import (
    analyze_coin, scan_all_coins, get_db_stats
)
from data.cache import cache
from data.fetcher import get_fear_greed, get_news_filter
from trade.state import state_manager
from trade.manager import trade_manager
from trade.risk import risk_guard
from trade.orders import get_current_price
from backtest.engine import run_backtest
from scheduler import get_next_scan_epoch
from config import cfg
import traceback
import logging
import math

log = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════════════════
# SERIALIZER
# ═══════════════════════════════════════════════════════
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
    try:
        import numpy as np
        if isinstance(obj, np.integer):  return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray):  return obj.tolist()
    except:
        pass
    try:
        import pandas as pd
        if isinstance(obj, pd.Series):    return obj.tolist()
        if isinstance(obj, pd.DataFrame): return obj.to_dict()
        if pd.isna(obj):                  return None
    except:
        pass
    return str(obj)


# ═══════════════════════════════════════════════════════
# COLOR PALETTE — WCAG AA on white
# ═══════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════
# FORMAT HELPERS
# ═══════════════════════════════════════════════════════
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
    except:
        return "--"


def fmt_pnl(n) -> str:
    if n is None:
        return "--"
    try:
        n    = float(n)
        sign = "+" if n >= 0 else ""
        return f"{sign}${abs(n):.4f}"
    except:
        return "--"


def fmt_pct(n) -> str:
    if n is None:
        return "--"
    try:
        n    = float(n)
        sign = "+" if n >= 0 else ""
        return f"{sign}{n:.2f}%"
    except:
        return "--"


def fmt_duration(opened_at) -> str:
    if not opened_at:
        return "--"
    try:
        if isinstance(opened_at, str):
            opened_at = datetime.fromisoformat(
                opened_at.replace("Z", "+00:00")
            )
        diff       = datetime.now(timezone.utc) - \
                     opened_at.replace(tzinfo=timezone.utc)
        total_mins = int(diff.total_seconds() / 60)
        hrs        = total_mins // 60
        mins       = total_mins % 60
        days       = hrs // 24
        if days > 0:  return f"{days}d {hrs % 24}h"
        if hrs > 0:   return f"{hrs}h {mins}m"
        return f"{total_mins}m"
    except:
        return "--"


def grade_color(grade: str) -> str:
    return {
        "A+": C["green"],
        "A":  C["blue"],
        "B":  C["orange"],
        "C":  C["yellow_dark"],
        "F":  C["muted"]
    }.get(grade, C["muted"])


def pnl_color(n) -> str:
    try:
        return C["green_dark"] if float(n) >= 0 else C["red_dark"]
    except:
        return C["muted"]


def progress_color(pct: float) -> str:
    if pct >= 75: return C["green"]
    if pct >= 50: return C["blue"]
    if pct >= 25: return C["orange"]
    return C["red"]


def health_color(state: str) -> str:
    return {
        "HEALTHY":     C["green_dark"],
        "WARNING":     C["orange"],
        "INVALIDATED": C["red_dark"]
    }.get(state, C["muted"])


def health_emoji(state: str) -> str:
    return {
        "HEALTHY":     "✅",
        "WARNING":     "⚠️",
        "INVALIDATED": "🚨"
    }.get(state, "—")


# ═══════════════════════════════════════════════════════
# TP1 HIT DETECTION
# sl_price ≈ entry_price means TP1 was hit
# ═══════════════════════════════════════════════════════
def detect_tp1_hit(trade) -> bool:
    entry = trade.entry_price
    sl    = trade.sl_price
    if not entry or not sl:
        return False
    return abs(sl - entry) / entry < 0.001


# ═══════════════════════════════════════════════════════
# BUILD LADDER
# ═══════════════════════════════════════════════════════
def build_ladder(trade, current: float) -> list:
    entry   = trade.entry_price
    sl      = trade.sl_price
    tp1     = trade.tp1_price
    tp2     = trade.tp2_price
    is_long = trade.direction == "LONG"
    tp1_hit = detect_tp1_hit(trade)

    def dist_pct(a, b) -> str:
        if not a or not b or b == 0:
            return ""
        pct  = (a - b) / b * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.2f}%"

    levels = []

    levels.append({
        "pos":         tp2,
        "cls":         "tp2",
        "label":       "TP2",
        "price":       fmt_price(tp2),
        "dist":        dist_pct(tp2, current),
        "color":       C["green_dark"],
        "badge":       "🎯 +2.5R",
        "badge_style": f"background:{C['green_bg']};color:{C['green_dark']}",
        "is_current":  False,
        "is_hit":      False
    })

    tp1_color = C["muted"] if tp1_hit else C["green_dark"]
    levels.append({
        "pos":         tp1,
        "cls":         "tp1",
        "label":       "TP1",
        "price":       fmt_price(tp1),
        "dist":        dist_pct(tp1, current),
        "color":       tp1_color,
        "badge":       "✅ HIT" if tp1_hit else "🎯 +1.5R",
        "badge_style": (
            f"background:rgba(110,110,115,0.1);color:{C['muted']}"
            if tp1_hit else
            f"background:{C['green_bg']};color:{C['green_dark']}"
        ),
        "is_current":  False,
        "is_hit":      tp1_hit
    })

    levels.append({
        "pos":         current,
        "cls":         "current",
        "label":       "NOW",
        "price":       fmt_price(current),
        "dist":        "",
        "color":       C["blue"],
        "badge":       "📍 LIVE",
        "badge_style": f"background:{C['blue_bg']};color:{C['blue']}",
        "is_current":  True,
        "is_hit":      False
    })

    levels.append({
        "pos":         entry,
        "cls":         "entry",
        "label":       "ENTRY",
        "price":       fmt_price(entry),
        "dist":        dist_pct(entry, current),
        "color":       C["orange"],
        "badge":       "✅ FILLED",
        "badge_style": f"background:{C['orange_bg']};color:{C['orange']}",
        "is_current":  False,
        "is_hit":      False
    })

    sl_label = "BE"        if tp1_hit else "SL"
    sl_badge = "🔒 B/E"    if tp1_hit else "🛑 STOP"
    sl_color = C["orange"] if tp1_hit else C["red_dark"]
    sl_bg    = C["orange_bg"] if tp1_hit else C["red_bg"]

    levels.append({
        "pos":         sl,
        "cls":         "sl",
        "label":       sl_label,
        "price":       fmt_price(sl),
        "dist":        dist_pct(sl, current),
        "color":       sl_color,
        "badge":       sl_badge,
        "badge_style": f"background:{sl_bg};color:{sl_color}",
        "is_current":  False,
        "is_hit":      False
    })

    levels.sort(key=lambda x: x["pos"] or 0, reverse=is_long)
    return levels


# ═══════════════════════════════════════════════════════
# BUILD PROGRESS
# ═══════════════════════════════════════════════════════
def build_progress(trade, current: float) -> dict:
    entry   = trade.entry_price
    sl      = trade.sl_price
    tp1     = trade.tp1_price
    tp2     = trade.tp2_price
    is_long = trade.direction == "LONG"
    tp1_hit = detect_tp1_hit(trade)

    tp2_hit = False
    if tp2 and current:
        tp2_hit = (current >= tp2 if is_long else current <= tp2)

    if tp2_hit:
        return {
            "pct":         100,
            "color":       C["green"],
            "label":       "🏆 TP2 Hit — Full Win!",
            "left_label":  fmt_price(entry),
            "mid_label":   "TP1 ✅",
            "right_label": fmt_price(tp2) + " ✅",
            "phase":       3,
            "phase_label": "Phase 3 — Complete",
            "tp1_hit":     True,
            "tp2_hit":     True
        }

    if tp1_hit:
        total = abs(tp2 - entry) if tp2 and entry else 0
        if total == 0:
            pct = 0
        elif is_long:
            pct = (current - entry) / total * 100
        else:
            pct = (entry - current) / total * 100
        pct       = max(0, min(100, pct))
        remaining = abs(tp2 - current) if tp2 and current else 0
        label = (
            f"{'📈' if is_long else '📉'} {pct:.0f}% to TP2 — "
            f"Risk Free ✅ ({fmt_price(remaining)} remaining)"
        )
        return {
            "pct":         round(pct),
            "color":       C["green"],
            "label":       label,
            "left_label":  f"BE: {fmt_price(entry)}",
            "mid_label":   "TP1 ✅",
            "right_label": f"TP2: {fmt_price(tp2)}",
            "phase":       2,
            "phase_label": "Phase 2 — Risk Free",
            "tp1_hit":     True,
            "tp2_hit":     False
        }

    total = abs(tp1 - sl) if tp1 and sl else 0
    if total == 0:
        pct = 0
    elif is_long:
        pct = (current - sl) / total * 100
    else:
        pct = (sl - current) / total * 100
    pct = max(0, min(100, pct))

    if is_long:
        if tp1 and current >= tp1:
            label = "🎯 TP1 Reached!"
        elif entry and current > entry:
            rng   = (tp1 - entry) if tp1 and entry else 1
            inner = (current - entry) / rng * 100 if rng > 0 else 0
            away  = fmt_price(tp1 - current) if tp1 else "--"
            label = f"📈 In profit — {inner:.0f}% to TP1 ({away} away)"
        elif entry and current == entry:
            label = "⚖️ At entry — breakeven"
        else:
            rng   = (entry - sl) if entry and sl else 1
            inner = (entry - current) / rng * 100 if rng > 0 else 0
            above = fmt_price(current - sl) if sl else "--"
            label = f"📉 {inner:.0f}% toward SL ({above} above SL)"
    else:
        if tp1 and current <= tp1:
            label = "🎯 TP1 Reached!"
        elif entry and current < entry:
            rng   = (entry - tp1) if entry and tp1 else 1
            inner = (entry - current) / rng * 100 if rng > 0 else 0
            away  = fmt_price(current - tp1) if tp1 else "--"
            label = f"📉 In profit — {inner:.0f}% to TP1 ({away} away)"
        elif entry and current == entry:
            label = "⚖️ At entry — breakeven"
        else:
            rng   = (sl - entry) if sl and entry else 1
            inner = (current - entry) / rng * 100 if rng > 0 else 0
            below = fmt_price(sl - current) if sl else "--"
            label = f"📈 {inner:.0f}% toward SL ({below} below SL)"

    return {
        "pct":         round(pct),
        "color":       progress_color(pct),
        "label":       label,
        "left_label":  fmt_price(sl),
        "mid_label":   fmt_price(entry),
        "right_label": fmt_price(tp1),
        "phase":       1,
        "phase_label": "Phase 1 — To TP1",
        "tp1_hit":     False,
        "tp2_hit":     False
    }


# ═══════════════════════════════════════════════════════
# BUILD TRADE DATA
# Includes health state and explanation.
# ═══════════════════════════════════════════════════════
def build_trade_data(trade, current: float) -> dict:
    is_long  = trade.direction == "LONG"
    tp1_hit  = detect_tp1_hit(trade)

    upnl     = risk_guard.calculate_unrealized_pnl(
        direction     = trade.direction,
        entry_price   = trade.entry_price,
        current_price = current,
        pos_size      = trade.position_size
    )
    capital  = cfg.CAPITAL
    pnl_pct  = (upnl / capital * 100) if capital else 0
    move_amt = current - trade.entry_price
    move_pct = (move_amt / trade.entry_price * 100) if trade.entry_price else 0

    dist_sl   = abs(current - trade.sl_price)  if trade.sl_price  else 0
    dist_sl_p = dist_sl / current * 100        if current         else 0
    dist_tp1  = abs(current - trade.tp1_price) if trade.tp1_price else 0
    dist_tp1p = dist_tp1 / current * 100       if current         else 0

    pos_size = trade.position_size or 0
    risk_amt = trade.risk_amt or 0

    tp1_rew = pos_size * (
        abs(trade.tp1_price - trade.entry_price) / trade.entry_price
    ) if trade.entry_price and trade.tp1_price else 0

    tp2_rew = pos_size * (
        abs(trade.tp2_price - trade.entry_price) / trade.entry_price
    ) if trade.entry_price and trade.tp2_price else 0

    rr = round(tp1_rew / risk_amt, 1) if risk_amt > 0 else 0

    dir_color  = C["green_dark"] if is_long else C["red_dark"]
    dir_border = C["green"]      if is_long else C["red"]

    header_bg = (
        "linear-gradient(135deg,rgba(52,199,89,0.06) 0%,rgba(255,255,255,0) 100%)"
        if is_long else
        "linear-gradient(135deg,rgba(255,59,48,0.06) 0%,rgba(255,255,255,0) 100%)"
    )

    prog        = build_progress(trade, current)
    phase       = prog["phase"]
    phase_badge = (
        "🏆 TP2 Phase" if phase == 3 else
        "⚡ Risk Free" if phase == 2 else
        "🎯 To TP1"
    )
    phase_color = C["green_dark"] if phase >= 2 else C["blue"]

    sl_label = "BE"        if tp1_hit else "SL"
    sl_color = C["orange"] if tp1_hit else C["red_dark"]

    in_profit = (
        (is_long  and current > trade.entry_price) or
        (not is_long and current < trade.entry_price)
    )
    current_color = C["green_dark"] if in_profit else C["red_dark"]

    # Health state from state_manager
    health_state = state_manager.health_state
    health_data  = state_manager.health_data

    # Explanation from cached scan result
    explanation = {}
    cached = cache.get(f"signal_{trade.coin}")
    if cached:
        explanation = cached.get("explanation", {})

    return {
        "id":             trade.id,
        "coin":           f"{trade.coin}USDT",
        "direction":      trade.direction,
        "dir_emoji":      "📈" if is_long else "📉",
        "dir_color":      dir_color,
        "dir_border":     dir_border,
        "header_bg":      header_bg,
        "grade":          trade.grade,
        "grade_color":    grade_color(trade.grade),
        "state":          trade.state,
        "duration":       fmt_duration(trade.opened_at),
        "opened_at":      trade.opened_at.isoformat() if trade.opened_at else None,
        "phase_badge":    phase_badge,
        "phase_color":    phase_color,
        "tp1_hit":        tp1_hit,
        "pnl":            fmt_pnl(upnl),
        "pnl_color":      pnl_color(upnl),
        "pnl_pct":        fmt_pct(pnl_pct) + " of capital",
        "pnl_positive":   upnl >= 0,
        "current_price":  fmt_price(current),
        "current_color":  current_color,
        "entry_price":    fmt_price(trade.entry_price),
        "sl_price":       fmt_price(trade.sl_price),
        "sl_label":       sl_label,
        "sl_color":       sl_color,
        "tp1_price":      fmt_price(trade.tp1_price),
        "tp2_price":      fmt_price(trade.tp2_price),
        "move_pct":       fmt_pct(move_pct),
        "move_color":     pnl_color(move_pct),
        "dist_to_sl":     f"{fmt_price(dist_sl)} ({dist_sl_p:.2f}%)",
        "dist_to_tp1":    f"{fmt_price(dist_tp1)} ({dist_tp1p:.2f}%)",
        "risk_amt":       f"${risk_amt:.4f}",
        "tp1_reward":     f"${tp1_rew:.4f}",
        "tp2_reward":     f"${tp2_rew:.4f}",
        "position_size":  f"${pos_size:.2f}",
        "margin_used":    f"${trade.margin_used:.2f}" if trade.margin_used else "--",
        "leverage":       f"{trade.leverage}x",
        "rr_ratio":       f"1:{rr}",
        "progress":       prog,
        "ladder":         build_ladder(trade, current),
        "entry_order_id": trade.entry_order_id,
        "sl_order_id":    trade.sl_order_id,
        "tp1_order_id":   trade.tp1_order_id,
        "tp2_order_id":   trade.tp2_order_id,
        # Health engine output
        "health_state":   health_state,
        "health_color":   health_color(health_state),
        "health_emoji":   health_emoji(health_state),
        "health_warnings": health_data.get("warnings", []),
        "health_failures": health_data.get("failures", []),
        "health_checks":   health_data.get("checks", []),
        "health_summary":  health_data.get("summary", ""),
        # Explanation
        "thesis":          explanation.get("thesis", ""),
        "risk_thesis":     explanation.get("risk_thesis", ""),
        "confidence":      explanation.get("confidence", 0),
        "confidence_label":explanation.get("confidence_label", "")
    }


# ═══════════════════════════════════════════════════════
# BUILD RISK DATA
# ═══════════════════════════════════════════════════════
def build_risk_data(risk) -> dict:
    daily_cap = cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT

    if not risk:
        return {
            "trades_label":      "0/3",
            "trades_bar_pct":    0,
            "trades_bar_color":  C["blue"],
            "loss_label":        "$0.0000",
            "loss_bar_pct":      0,
            "loss_bar_color":    C["green"],
            "pnl_label":         "$0.0000",
            "pnl_color":         C["green_dark"],
            "pnl_bar_pct":       0,
            "remaining_trades":  cfg.MAX_TRADES_PER_DAY,
            "remaining_loss":    f"${daily_cap:.4f}",
            "cap_status":        "✅ Active",
            "cap_color":         C["green_dark"]
        }

    trades_taken = risk.get("trades_taken", 0)
    total_pnl    = risk.get("total_pnl", 0)
    total_loss   = risk.get("total_loss", 0)
    cap_hit      = risk.get("cap_hit", False)

    loss_pct    = min(100, abs(total_loss) / daily_cap * 100) if daily_cap > 0 else 0
    pnl_bar_pct = min(100, abs(total_pnl)  / daily_cap * 100) if daily_cap > 0 else 0

    return {
        "trades_label":     f"{trades_taken}/3",
        "trades_bar_pct":   round(trades_taken / cfg.MAX_TRADES_PER_DAY * 100),
        "trades_bar_color": C["red"] if trades_taken >= cfg.MAX_TRADES_PER_DAY else C["blue"],
        "loss_label":       f"${abs(total_loss):.4f}",
        "loss_bar_pct":     round(loss_pct),
        "loss_bar_color":   C["red"] if loss_pct >= 80 else C["orange"] if loss_pct >= 50 else C["green"],
        "pnl_label":        fmt_pnl(total_pnl),
        "pnl_color":        pnl_color(total_pnl),
        "pnl_bar_pct":      round(pnl_bar_pct),
        "remaining_trades": risk.get("remaining_trades", cfg.MAX_TRADES_PER_DAY),
        "remaining_loss":   f"${risk.get('remaining_loss', daily_cap):.4f}",
        "cap_status":       "🚫 Cap Hit" if cap_hit else "✅ Active",
        "cap_color":        C["red_dark"] if cap_hit else C["green_dark"]
    }


# ═══════════════════════════════════════════════════════
# BUILD PERFORMANCE DATA
# ═══════════════════════════════════════════════════════
def build_performance_data(stats: dict, trades: list) -> dict:
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
        "a_detail":       "0W · 0L · 0 trades"
    }

    if not stats:
        return empty

    wr     = stats.get("win_rate", 0)
    tp     = stats.get("total_pnl", 0)
    closed = [t for t in trades if t.get("outcome") != "pending"]

    gross_p = sum(t.get("pnl_raw", 0) or 0 for t in closed if (t.get("pnl_raw") or 0) > 0)
    gross_l = abs(sum(t.get("pnl_raw", 0) or 0 for t in closed if (t.get("pnl_raw") or 0) < 0))
    pf      = round(gross_p / gross_l, 2) if gross_l > 0 else 0

    pnls   = [t.get("pnl_raw", 0) or 0 for t in closed]
    best   = max(pnls) if pnls else 0
    best_t = next((t for t in closed if (t.get("pnl_raw") or 0) == best), None)

    peak   = 0
    max_dd = 0
    equity = 0
    for t in sorted(closed, key=lambda x: x.get("closed_at") or ""):
        equity += t.get("pnl_raw", 0) or 0
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    bg    = stats.get("by_grade", {})
    ap    = bg.get("A+", {})
    a     = bg.get("A", {})
    ap_wr = ap.get("win_rate", 0)
    a_wr  = a.get("win_rate", 0)

    return {
        "win_rate":       f"{wr}%",
        "win_rate_color": C["green_dark"] if wr >= 55 else C["orange"] if wr >= 45 else C["red_dark"],
        "win_rate_sub":   f"{stats.get('closed', 0)} closed",
        "total_pnl":      fmt_pnl(tp),
        "pnl_color":      pnl_color(tp),
        "pnl_sub":        f"{stats.get('wins',0)}W · {stats.get('losses',0)}L",
        "profit_factor":  str(pf) if pf > 0 else "∞",
        "pf_sub":         f"${gross_p:.2f} / ${gross_l:.2f}",
        "best_trade":     fmt_pnl(best),
        "best_sub":       best_t.get("coin", "--") if best_t else "--",
        "max_drawdown":   f"{max_dd:.1f}%",
        "dd_color":       C["green_dark"] if max_dd < 10 else C["orange"] if max_dd < 20 else C["red_dark"],
        "dd_sub":         f"peak: ${peak:.2f}",
        "aplus_wr":       f"{ap_wr}%",
        "aplus_bar":      ap_wr,
        "aplus_detail":   f"{ap.get('wins',0)}W · {(ap.get('total',0) - ap.get('wins',0))}L · {ap.get('total',0)} trades · {fmt_pnl(ap.get('total_pnl',0))}",
        "a_wr":           f"{a_wr}%",
        "a_bar":          a_wr,
        "a_detail":       f"{a.get('wins',0)}W · {(a.get('total',0) - a.get('wins',0))}L · {a.get('total',0)} trades · {fmt_pnl(a.get('total_pnl',0))}"
    }


# ═══════════════════════════════════════════════════════
# BUILD RADAR DATA
# ═══════════════════════════════════════════════════════
def build_radar_data(results: list) -> list:
    radar = []
    for r in results:
        grade  = r.get("grade", "F")
        dir_   = r.get("direction", "--")
        score  = r.get("score", 0)
        market = r.get("market", {})
        price  = market.get("price", 0)
        change = market.get("change24", 0)

        explanation = r.get("explanation", {})
        conf_label  = explanation.get("confidence_label", "")

        radar.append({
            "coin":          r.get("coin", "--"),
            "grade":         grade,
            "grade_color":   grade_color(grade),
            "direction":     dir_,
            "dir_emoji":     "📈" if dir_ == "LONG" else "📉" if dir_ == "SHORT" else "👁" if dir_ == "WATCH" else "—",
            "dir_color":     C["green_dark"] if dir_ == "LONG" else C["red_dark"] if dir_ == "SHORT" else C["orange"] if dir_ == "WATCH" else C["muted"],
            "score":         score,
            "score_pct":     min(100, score),
            "price":         fmt_price(price),
            "change":        fmt_pct(change),
            "change_color":  C["green_dark"] if change >= 0 else C["red_dark"],
            "tradeable":     grade in ["A+", "A"] and dir_ in ["LONG", "SHORT"],
            "confidence":    conf_label
        })

    return radar


# ═══════════════════════════════════════════════════════
# BUILD SIGNAL QUEUE
# Includes explanation fields.
# ═══════════════════════════════════════════════════════
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

        explanation = r.get("explanation", {})

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
            "tp2":              fmt_price(sig.get("tp2")),
            "risk_amt":         f"${sig.get('risk_amt', 0):.2f}",
            "sl_pct":           f"{sig.get('sl_pct', 0):.2f}%",
            "regime":           r.get("regime", "--"),
            "session":          r.get("session", "--"),
            "thesis":           explanation.get("thesis", ""),
            "risk_thesis":      explanation.get("risk_thesis", ""),
            "confidence_label": explanation.get("confidence_label", ""),
            "no_trade_reason":  explanation.get("no_trade_reason", "")
        })

    return queue


# ═══════════════════════════════════════════════════════
# BUILD HISTORY DATA
# ═══════════════════════════════════════════════════════
def build_history_data(trades: list) -> list:
    result = []
    for t in trades[:10]:
        pnl     = t.get("pnl") or 0
        outcome = t.get("outcome", "pending")
        is_long = t.get("direction") == "LONG"

        try:
            pnl_float = float(pnl)
        except:
            pnl_float = 0.0

        result.append({
            "coin":          t.get("coin", "--"),
            "direction":     t.get("direction", "--"),
            "dir_emoji":     "📈" if is_long else "📉",
            "dir_color":     C["green_dark"] if is_long else C["red_dark"],
            "grade":         t.get("grade", "--"),
            "outcome":       outcome,
            "outcome_emoji": "✅" if outcome == "win" else "❌" if outcome == "loss" else "⏹",
            "border_color":  C["green"] if outcome == "win" else C["red"] if outcome == "loss" else "rgba(0,0,0,0.1)",
            "pnl":           fmt_pnl(pnl_float),
            "pnl_raw":       round(pnl_float, 4),
            "pnl_color":     pnl_color(pnl_float),
            "close_reason":  t.get("close_reason", "--"),
            "closed_at":     t.get("closed_at", "--")
        })

    return result


# ═══════════════════════════════════════════════════════
# BUILD HEADER DATA
# ═══════════════════════════════════════════════════════
def build_header_data(risk_stats: dict, stats: dict) -> dict:
    today_pnl   = risk_stats.get("total_pnl", 0)
    trades_left = risk_stats.get("remaining_trades", cfg.MAX_TRADES_PER_DAY)
    wr          = stats.get("win_rate", 0) if stats else 0

    return {
        "capital":           f"${cfg.CAPITAL}",
        "leverage":          f"{cfg.LEVERAGE}x",
        "today_pnl":         fmt_pnl(today_pnl),
        "today_pnl_color":   pnl_color(today_pnl),
        "trades_left":       str(trades_left),
        "trades_left_color": C["red_dark"] if trades_left == 0 else C["text"],
        "win_rate":          f"{wr}%",
        "win_rate_color":    C["green_dark"] if wr >= 55 else C["orange"] if wr >= 45 else C["red_dark"],
        "mode":              "PAPER" if cfg.PAPER_TRADING else "LIVE",
        "mode_color":        C["blue"] if cfg.PAPER_TRADING else C["red_dark"]
    }


# ═══════════════════════════════════════════════════════
# DASHBOARD ENDPOINT
# Single call — returns everything display-ready.
# Includes explanation, health, UTC next scan epoch.
# ═══════════════════════════════════════════════════════
@router.get("/dashboard")
async def dashboard():
    try:
        from database import SessionLocal
        from database import Trade as TradeModel

        trade_state = "idle"
        trade_data  = None

        if not state_manager.is_idle:
            state_manager.refresh()
            trade = state_manager.current_trade

            if trade and trade.is_active:
                current     = get_current_price(trade.coin)
                trade_state = trade.state
                trade_data  = build_trade_data(trade, current)

        risk_stats = risk_guard.get_daily_stats()
        risk_data  = build_risk_data(risk_stats)
        stats      = get_db_stats()

        db = SessionLocal()
        try:
            trades_raw = db.query(TradeModel).filter(
                TradeModel.is_active == False
            ).order_by(
                TradeModel.closed_at.desc()
            ).limit(10).all()

            trades_list = [{
                "coin":         t.coin,
                "direction":    t.direction,
                "grade":        t.grade,
                "pnl":          t.pnl,
                "outcome":      t.outcome,
                "close_reason": t.close_reason,
                "closed_at":    t.closed_at.isoformat() if t.closed_at else None
            } for t in trades_raw]
        finally:
            db.close()

        perf_data    = build_performance_data(stats, trades_list)
        history_data = build_history_data(trades_list)

        radar_data = []
        queue_data = []
        last_scan  = "--"

        cached_results = []
        for coin in cfg.COINS:
            cached = cache.get(f"signal_{coin}")
            if cached:
                cached_results.append(cached)

        if cached_results:
            cached_results.sort(
                key=lambda x: x.get("score", 0),
                reverse=True
            )
            radar_data = build_radar_data(cached_results)
            queue_data = build_signal_queue(cached_results)
            last_scan  = "From cache"

        header_data = build_header_data(risk_stats, stats)

        # UTC next scan epoch — frontend derives countdown from this
        next_scan_epoch = get_next_scan_epoch()

        return JSONResponse(
            content=make_serializable({
                "state":           trade_state,
                "trade":           trade_data,
                "risk":            risk_data,
                "performance":     perf_data,
                "history":         history_data,
                "radar":           radar_data,
                "queue":           queue_data,
                "header":          header_data,
                "last_scan":       last_scan,
                "next_scan_epoch": next_scan_epoch,
                "timestamp":       datetime.now(timezone.utc).isoformat()
            })
        )

    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════
# ANALYZE ENDPOINT
# ═══════════════════════════════════════════════════════
@router.get("/analyze/{coin}")
async def analyze(
    coin:     str,
    capital:  float = cfg.CAPITAL,
    leverage: int   = cfg.LEVERAGE
):
    coin = coin.upper()
    if coin not in cfg.COINS:
        raise HTTPException(400, f"{coin} not supported")
    try:
        result = await analyze_coin(coin, capital, leverage)
        if "error" in result:
            raise HTTPException(500, result["error"])
        return JSONResponse(content=make_serializable(result))
    except HTTPException:
        raise
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════
# SCAN ENDPOINT
# ═══════════════════════════════════════════════════════
@router.get("/scan")
async def scan():
    try:
        results = await scan_all_coins()
        return JSONResponse(content={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "count":     len(results),
            "results":   make_serializable(results)
        })
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════
# SIGNALS ENDPOINT
# ═══════════════════════════════════════════════════════
@router.get("/signals")
async def get_signals(
    limit: int = 50,
    grade: str = None,
    coin:  str = None,
    db: Session = Depends(get_db)
):
    try:
        q = db.query(SignalModel).order_by(SignalModel.timestamp.desc())
        if grade:
            q = q.filter(SignalModel.grade == grade.upper())
        if coin:
            q = q.filter(SignalModel.coin == coin.upper())

        signals = q.limit(limit).all()
        result  = []
        for s in signals:
            result.append({
                "id":          s.id,
                "timestamp":   s.timestamp.isoformat() if s.timestamp else None,
                "coin":        s.coin,
                "direction":   s.direction,
                "grade":       s.grade,
                "score":       s.score,
                "signal_type": s.signal_type,
                "entry":       s.entry,
                "sl":          s.sl,
                "tp1":         s.tp1,
                "tp2":         s.tp2,
                "risk_amt":    s.risk_amt,
                "regime":      s.regime,
                "session":     s.session,
                "outcome":     s.outcome,
                "exit_price":  s.exit_price,
                "pnl":         s.pnl
            })
        return JSONResponse(content=result)
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════
# STATS ENDPOINT
# ═══════════════════════════════════════════════════════
@router.get("/stats")
async def get_stats():
    try:
        stats = get_db_stats()
        return JSONResponse(content=make_serializable(stats))
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════
# TRADE ENDPOINTS
# ═══════════════════════════════════════════════════════
@router.get("/trade/status")
async def trade_status():
    try:
        if state_manager.is_idle:
            return JSONResponse(content={"state": "idle", "trade": None})

        state_manager.refresh()
        trade   = state_manager.current_trade
        current = get_current_price(trade.coin)

        return JSONResponse(content={
            "state": trade.state,
            "trade": make_serializable(build_trade_data(trade, current))
        })
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.post("/trade/close")
async def close_trade():
    try:
        result = await trade_manager.manual_close()
        if not result["success"]:
            raise HTTPException(400, result["reason"])
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/trade/history")
async def trade_history(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    try:
        trades = db.query(TradeModel).filter(
            TradeModel.is_active == False
        ).order_by(TradeModel.closed_at.desc()).limit(limit).all()

        result = []
        for t in trades:
            result.append({
                "id":            t.id,
                "coin":          t.coin,
                "direction":     t.direction,
                "grade":         t.grade,
                "entry_price":   t.entry_price,
                "exit_price":    t.exit_price,
                "sl_price":      t.sl_price,
                "tp1_price":     t.tp1_price,
                "tp2_price":     t.tp2_price,
                "pnl":           t.pnl,
                "outcome":       t.outcome,
                "close_reason":  t.close_reason,
                "risk_amt":      t.risk_amt,
                "position_size": t.position_size,
                "margin_used":   t.margin_used,
                "leverage":      t.leverage,
                "opened_at":     t.opened_at.isoformat() if t.opened_at else None,
                "closed_at":     t.closed_at.isoformat() if t.closed_at else None
            })
        return JSONResponse(content=result)
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════
# RISK ENDPOINTS
# ═══════════════════════════════════════════════════════
@router.get("/risk/daily")
async def daily_risk():
    try:
        stats = risk_guard.get_daily_stats()
        return JSONResponse(content=make_serializable(stats))
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════
# MARKET ENDPOINTS
# ═══════════════════════════════════════════════════════
@router.get("/market/{coin}")
async def market(coin: str):
    coin   = coin.upper()
    cached = cache.get(f"signal_{coin}")
    if cached:
        return JSONResponse(content=make_serializable(cached["market"]))
    raise HTTPException(404, "Run scan first")


@router.get("/fear-greed")
async def fear_greed():
    try:
        data = await get_fear_greed()
        return JSONResponse(content=make_serializable(data))
    except Exception as e:
        return JSONResponse(content={"value": 50, "label": "Neutral"})


@router.get("/macro-events")
async def macro_events():
    try:
        data = await get_news_filter()
        return JSONResponse(content=make_serializable(data))
    except Exception as e:
        return JSONResponse(content=[])


# ═══════════════════════════════════════════════════════
# BACKTEST ENDPOINTS
# ═══════════════════════════════════════════════════════
@router.get("/backtest/{coin}")
async def backtest(
    coin:     str,
    capital:  float = cfg.CAPITAL,
    leverage: int   = cfg.LEVERAGE
):
    coin = coin.upper()
    if coin not in cfg.COINS:
        raise HTTPException(400, f"{coin} not supported")
    try:
        result = run_backtest(coin=coin, capital=capital, leverage=leverage)
        if "error" in result:
            raise HTTPException(400, result["error"])
        return JSONResponse(content=make_serializable(result))
    except HTTPException:
        raise
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/backtest/all/run")
async def backtest_all(
    capital:  float = cfg.CAPITAL,
    leverage: int   = cfg.LEVERAGE
):
    results = []
    for coin in cfg.COINS:
        try:
            r = run_backtest(coin=coin, capital=capital, leverage=leverage)
            if "error" not in r:
                results.append(r)
        except Exception as e:
            log.error(f"Backtest error {coin}: {e}")
            continue

    results.sort(key=lambda x: x.get("win_rate", 0), reverse=True)

    return JSONResponse(content=make_serializable({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "count":     len(results),
        "results":   results
    }))


@router.get("/backtest/history/all")
async def backtest_history(db: Session = Depends(get_db)):
    try:
        rows = db.query(BacktestResult).order_by(
            BacktestResult.run_at.desc()
        ).limit(50).all()

        result = []
        for r in rows:
            result.append({
                "id":           r.id,
                "run_at":       r.run_at.isoformat() if r.run_at else None,
                "coin":         r.coin,
                "period_start": r.period_start,
                "period_end":   r.period_end,
                "total_trades": r.total_trades,
                "wins":         r.wins,
                "losses":       r.losses,
                "win_rate":     r.win_rate,
                "total_pnl":    r.total_pnl,
                "max_drawdown": r.max_drawdown,
                "notes":        r.notes
            })
        return JSONResponse(content=make_serializable(result))
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════
# HEALTH ENDPOINT
# ═══════════════════════════════════════════════════════
@router.get("/health")
async def health():
    trade = state_manager.current_trade
    return JSONResponse(content={
        "status":       "ok",
        "timestamp":    datetime.now(timezone.utc).isoformat(),
        "trade_state":  state_manager.current_state,
        "active_coin":  trade.coin if trade else None,
        "paper_mode":   cfg.PAPER_TRADING,
        "health_state": state_manager.health_state
    })


# ═══════════════════════════════════════════════════════
# FACTOR ANALYSIS ENDPOINT
# ═══════════════════════════════════════════════════════
@router.get("/analysis/factors")
async def factor_analysis():
    try:
        result = run_factor_analysis()
        return JSONResponse(content=make_serializable(result))
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))