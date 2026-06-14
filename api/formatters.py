import math
import logging
from datetime import datetime, timezone
from config import cfg
from trade.state import state_manager
from trade.risk import risk_guard, get_current_tier
from trade.orders import get_current_price, exchange as sync_exchange
from data.cache import cache

log = logging.getLogger(__name__)

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


def detect_tp1_hit(trade) -> bool:
    if trade.tp1_hit is not None:
        return trade.tp1_hit
    entry = trade.entry_price
    sl    = trade.sl_price
    if not entry or not sl:
        return False
    return abs(sl - entry) / entry < 0.001


def _get_live_upnl(coin: str) -> float | None:
    if cfg.PAPER_TRADING:
        return None
    try:
        positions = sync_exchange.fetch_positions([f"{coin}/USDT"])
        for pos in positions:
            if (pos.get("symbol") == f"{coin}/USDT" and
                    float(pos.get("contracts", 0) or 0) > 0):
                upnl = float(pos.get("unrealizedPnl", 0) or 0)
                log.debug(f"[LIVE] Binance uPnL for {coin}: ${upnl:.4f}")
                return upnl
    except Exception as e:
        log.warning(f"Binance position fetch failed for {coin}: {e}")
    return None


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
        label     = (
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

    total = abs(sl - tp1) if tp1 and sl else 0
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
        "left_label":  fmt_price(sl)    if is_long else fmt_price(tp1),
        "mid_label":   fmt_price(entry),
        "right_label": fmt_price(tp1)   if is_long else fmt_price(sl),
        "phase":       1,
        "phase_label": "Phase 1 — To TP1",
        "tp1_hit":     False,
        "tp2_hit":     False
    }


def build_trade_data(trade, current: float) -> dict:
    is_long  = trade.direction == "LONG"
    tp1_hit  = detect_tp1_hit(trade)
    tier     = get_current_tier()

    live_upnl = _get_live_upnl(trade.coin)
    if live_upnl is not None:
        upnl = live_upnl
    else:
        upnl = risk_guard.calculate_unrealized_pnl(
            direction     = trade.direction,
            entry_price   = trade.entry_price,
            current_price = current,
            pos_size      = trade.position_size
        )

    capital  = tier["balance"] or cfg.CAPITAL
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
        "linear-gradient(135deg,rgba(52,199,89,0.15) 0%,rgba(255,255,255,0) 40%)"
        if is_long else
        "linear-gradient(135deg,rgba(255,59,48,0.15) 0%,rgba(255,255,255,0) 40%)"
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

    health_state = state_manager.health_state_for(trade.id)
    health_data  = state_manager.health_data_for(trade.id)

    explanation = {}
    cached = cache.get_raw(f"signal_{trade.coin}")
    if cached:
        explanation = cached.get("explanation", {})

    pnl_source = "binance" if live_upnl is not None else "calculated"

    return {
        "id":               trade.id,
        "coin":             f"{trade.coin}USDT",
        "direction":        trade.direction,
        "dir_emoji":        "📈" if is_long else "📉",
        "dir_color":        dir_color,
        "dir_border":       dir_border,
        "header_bg":        header_bg,
        "grade":            trade.grade,
        "grade_color":      grade_color(trade.grade),
        "state":            trade.state,
        "duration":         fmt_duration(trade.opened_at),
        "opened_at":        trade.opened_at.isoformat() if trade.opened_at else None,
        "phase_badge":      phase_badge,
        "phase_color":      phase_color,
        "tp1_hit":          tp1_hit,
        "pnl":              fmt_pnl(upnl),
        "pnl_color":        pnl_color(upnl),
        "pnl_pct":          fmt_pct(pnl_pct) + " of capital",
        "pnl_positive":     upnl >= 0,
        "pnl_source":       pnl_source,
        "current_price":    fmt_price(current),
        "current_color":    current_color,
        "entry_price":      fmt_price(trade.entry_price),
        "sl_price":         fmt_price(trade.sl_price),
        "sl_label":         sl_label,
        "sl_color":         sl_color,
        "tp1_price":        fmt_price(trade.tp1_price),
        "tp2_price":        fmt_price(trade.tp2_price),
        "move_pct":         fmt_pct(move_pct),
        "move_color":       pnl_color(move_pct),
        "dist_to_sl":       f"{fmt_price(dist_sl)} ({dist_sl_p:.2f}%)",
        "dist_to_tp1":      f"{fmt_price(dist_tp1)} ({dist_tp1p:.2f}%)",
        "risk_amt":         f"${risk_amt:.4f}",
        "tp1_reward":       f"${tp1_rew:.4f}",
        "tp2_reward":       f"${tp2_rew:.4f}",
        "position_size":    f"${pos_size:.2f}",
        "margin_used":      f"${trade.margin_used:.2f}" if trade.margin_used else "--",
        "leverage":         f"{trade.leverage}x",
        "rr_ratio":         f"1:{rr}",
        "progress":         prog,
        "ladder":           build_ladder(trade, current),
        "entry_order_id":   trade.entry_order_id,
        "sl_order_id":      trade.sl_order_id,
        "tp1_order_id":     trade.tp1_order_id,
        "tp2_order_id":     trade.tp2_order_id,
        "health_state":     health_state,
        "health_color":     health_color(health_state),
        "health_emoji":     health_emoji(health_state),
        "health_warnings":  health_data.get("warnings", []),
        "health_failures":  health_data.get("failures", []),
        "health_checks":    health_data.get("checks", []),
        "health_summary":   health_data.get("summary", ""),
        "thesis":           explanation.get("thesis", ""),
        "risk_thesis":      explanation.get("risk_thesis", ""),
        "confidence":       explanation.get("confidence", 0),
        "confidence_label": explanation.get("confidence_label", ""),
        "tier":             tier["tier"],
        "balance":          f"${tier['balance']:.2f}"
    }


def build_all_trades_data(current_prices: dict = None) -> list:
    trades = []
    for trade in state_manager.active_trades.values():
        current = (current_prices or {}).get(trade.coin) or get_current_price(trade.coin)
        trades.append(build_trade_data(trade, current))
    return trades


def build_risk_data(risk) -> dict:
    tier      = get_current_tier()
    capital   = tier["balance"] or cfg.CAPITAL
    daily_cap = capital * cfg.DAILY_LOSS_CAP_PCT

    if not risk:
        return {
            "trades_label":     f"0/{tier['max_trades']}",
            "trades_bar_pct":   0,
            "trades_bar_color": C["blue"],
            "loss_label":       "$0.0000",
            "loss_bar_pct":     0,
            "loss_bar_color":   C["green"],
            "pnl_label":        "$0.0000",
            "pnl_color":        C["green_dark"],
            "pnl_bar_pct":      0,
            "remaining_trades": tier["max_trades"],
            "remaining_loss":   f"${daily_cap:.4f}",
            "cap_status":       "✅ Active",
            "cap_color":        C["green_dark"],
            "tier":             tier["tier"],
            "balance":          f"${capital:.2f}"
        }

    trades_taken = risk.get("trades_taken", 0)
    total_pnl    = risk.get("total_pnl", 0)
    total_loss   = risk.get("total_loss", 0)
    cap_hit      = risk.get("cap_hit", False)

    loss_pct    = min(100, abs(total_loss) / daily_cap * 100) if daily_cap > 0 else 0
    pnl_bar_pct = min(100, abs(total_pnl)  / daily_cap * 100) if daily_cap > 0 else 0

    return {
        "trades_label":     f"{trades_taken}/{tier['max_trades']}",
        "trades_bar_pct":   round(trades_taken / tier["max_trades"] * 100),
        "trades_bar_color": C["red"] if trades_taken >= tier["max_trades"] else C["blue"],
        "loss_label":       f"${abs(total_loss):.4f}",
        "loss_bar_pct":     round(loss_pct),
        "loss_bar_color":   C["red"] if loss_pct >= 80 else C["orange"] if loss_pct >= 50 else C["green"],
        "pnl_label":        fmt_pnl(total_pnl),
        "pnl_color":        pnl_color(total_pnl),
        "pnl_bar_pct":      round(pnl_bar_pct),
        "remaining_trades": risk.get("remaining_trades", tier["max_trades"]),
        "remaining_loss":   f"${risk.get('remaining_loss', daily_cap):.4f}",
        "cap_status":       "🚫 Cap Hit" if cap_hit else "✅ Active",
        "cap_color":        C["red_dark"] if cap_hit else C["green_dark"],
        "tier":             tier["tier"],
        "balance":          f"${capital:.2f}"
    }


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
        "win_rate_color": get_color("winrate", wr),
        "win_rate_sub":   f"{stats.get('closed', 0)} closed",
        "total_pnl":      fmt_pnl(tp),
        "pnl_color":      pnl_color(tp),
        "pnl_sub":        f"{stats.get('wins',0)}W · {stats.get('losses',0)}L",
        "profit_factor":  str(pf) if pf > 0 else "∞",
        "pf_sub":         f"${gross_p:.2f} / ${gross_l:.2f}",
        "best_trade":     fmt_pnl(best),
        "best_sub":       best_t.get("coin", "--") if best_t else "--",
        "max_drawdown":   f"{max_dd:.1f}%",
        "dd_color":       get_color("health", "HEALTHY") if max_dd < 10 else get_color("health", "WARNING") if max_dd < 20 else get_color("health", "INVALIDATED"),
        "dd_sub":         f"peak: ${peak:.2f}",
        "aplus_wr":       f"{ap_wr}%",
        "aplus_bar":      ap_wr,
        "aplus_detail":   f"{ap.get('wins',0)}W · {(ap.get('total',0) - ap.get('wins',0))}L · {ap.get('total',0)} trades · {fmt_pnl(ap.get('total_pnl',0))}",
        "a_wr":           f"{a_wr}%",
        "a_bar":          a_wr,
        "a_detail":       f"{a.get('wins',0)}W · {(a.get('total',0) - a.get('wins',0))}L · {a.get('total',0)} trades · {fmt_pnl(a.get('total_pnl',0))}"
    }


def build_radar_data(results: list) -> list:
    radar = []
    for r in results:
        grade  = r.get("grade", "F")
        dir_   = r.get("direction", "--")
        score  = r.get("score", 0)
        market = r.get("market", {})
        price  = market.get("price", 0)
        change = market.get("change24", 0)
        expl   = r.get("explanation", {})

        radar.append({
            "coin":        r.get("coin", "--"),
            "grade":       grade,
            "grade_color": grade_color(grade),
            "direction":   dir_,
            "dir_emoji":   "📈" if dir_ == "LONG" else "📉" if dir_ == "SHORT" else "👁" if dir_ == "WATCH" else "—",
            "dir_color":   C["green_dark"] if dir_ == "LONG" else C["red_dark"] if dir_ == "SHORT" else C["orange"] if dir_ == "WATCH" else C["muted"],
            "score":       score,
            "score_pct":   min(100, score),
            "price":       fmt_price(price),
            "change":      fmt_pct(change),
            "change_color":pnl_color(change),
            "tradeable":   grade in ["A+", "A"] and dir_ in ["LONG", "SHORT"],
            "confidence":  expl.get("confidence_label", "")
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
            "tp2":              fmt_price(sig.get("tp2")),
            "risk_amt":         f"${sig.get('risk_amt', 0):.2f}",
            "sl_pct":           f"{sig.get('sl_pct', 0):.2f}%",
            "regime":           r.get("regime", "--"),
            "session":          r.get("session", "--"),
            "thesis":           expl.get("thesis", ""),
            "risk_thesis":      expl.get("risk_thesis", ""),
            "confidence_label": expl.get("confidence_label", ""),
            "no_trade_reason":  expl.get("no_trade_reason", "")
        })

    return queue


def build_history_data(trades: list) -> list:
    result = []
    for t in trades[:10]:
        pnl     = t.get("pnl") or 0
        outcome = t.get("outcome", "pending")
        is_long = t.get("direction") == "LONG"

        try:
            pnl_float = float(pnl)
        except Exception:
            pnl_float = 0.0

        result.append({
            "id":               t.get("id"),
            "coin":             t.get("coin", "--"),
            "direction":        t.get("direction", "--"),
            "dir_emoji":        "📈" if is_long else "📉",
            "dir_color":        C["green_dark"] if is_long else C["red_dark"],
            "grade":            t.get("grade", "--"),
            "outcome":          outcome,
            "outcome_emoji":    "✅" if outcome == "win" else "❌" if outcome == "loss" else "⏹",
            "border_color":     C["green"] if outcome == "win" else C["red"] if outcome == "loss" else "rgba(0,0,0,0.1)",
            "pnl":              fmt_pnl(pnl_float),
            "pnl_raw":          round(pnl_float, 4),
            "pnl_color":        pnl_color(pnl_float),
            "close_reason":     t.get("close_reason", "--"),
            "closed_at":        t.get("closed_at", "--"),
            "opened_at":        t.get("opened_at"),
            "entry_price":      t.get("entry_price"),
            "exit_price":       t.get("exit_price"),
            "sl_price":         t.get("sl_price"),
            "tp1_price":        t.get("tp1_price"),
            "tp2_price":        t.get("tp2_price"),
            "risk_amt":         t.get("risk_amt"),
            "position_size":    t.get("position_size"),
            "leverage":         t.get("leverage"),
            "tp1_hit":          t.get("tp1_hit", False),
            "partial_pnl":      t.get("partial_pnl"),
            "regime_at_entry":  t.get("regime_at_entry"),
            "session_at_entry": t.get("session_at_entry"),
            "score_at_entry":   t.get("score_at_entry"),
            "balance_at_open":  t.get("balance_at_open"),
            "tier_at_open":     t.get("tier_at_open"),
            "health_at_close":  t.get("health_at_close"),
        })

    return result


def build_header_data(risk_stats: dict, stats: dict) -> dict:
    tier        = get_current_tier()
    today_pnl   = risk_stats.get("total_pnl", 0)
    trades_left = risk_stats.get("remaining_trades", tier["max_trades"])
    wr          = stats.get("win_rate", 0) if stats else 0
    import runtime_state as rs
    mode        = rs.get_trading_mode()

    return {
        "capital":           f"${tier['balance']:.2f}",
        "leverage":          f"{tier['leverage']}x",
        "today_pnl":         fmt_pnl(today_pnl),
        "today_pnl_color":   pnl_color(today_pnl),
        "trades_left":       str(trades_left),
        "trades_left_color": C["red_dark"] if trades_left == 0 else C["text"],
        "win_rate":          f"{wr}%",
        "win_rate_color":    get_color("winrate", wr),
        "mode":              "LIVE" if mode == "live" else "PAPER",
        "mode_color":        C["red_dark"] if mode == "live" else C["blue"],
        "paused":            state_manager.is_paused,
        "tier":              tier["tier"],
        "active_trades":     len(state_manager.active_trades),
        "max_trades":        tier["max_trades"]
    }