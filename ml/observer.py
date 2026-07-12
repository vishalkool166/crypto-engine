import json
import logging
from datetime import datetime, timezone
from database import get_session, SignalSnapshot
from config import cfg

log = logging.getLogger(__name__)


def capture(
    signal_id:     int,
    signal:        dict,
    d4h:           dict,
    d1h:           dict,
    d15m:          dict,
    balance:       float,
    sizing_result: dict,
) -> bool:
    try:
        from ml.version_registry import ensure_version_exists
        version = ensure_version_exists()

        sweep        = signal.get("sweep")        or {}
        zone         = signal.get("zone")         or {}
        trigger      = signal.get("trigger")      or {}
        factor_scores= signal.get("factor_scores")or {}

        now          = datetime.now(timezone.utc)
        day_of_week  = now.weekday()
        hour_of_day  = now.hour

        btc_data     = _get_btc_data()
        btc_direction= btc_data.get("trend", {}).get("cls", "neutral") if btc_data else "unknown"
        btc_adx      = float(btc_data.get("adx") or 0)                 if btc_data else 0.0
        btc_ema20    = float(btc_data.get("ema20") or 0)                if btc_data else 0.0
        btc_ema50    = float(btc_data.get("ema50") or 0)                if btc_data else 0.0
        btc_aligned  = (btc_ema20 > btc_ema50)                         if btc_data else False

        coin_adx     = float(d4h.get("adx")   or 0)
        coin_ema20   = float(d4h.get("ema20")  or 0)
        coin_ema50   = float(d4h.get("ema50")  or 0)
        atr_4h       = float(d4h.get("atr")    or 0)
        atr_1h       = float(d1h.get("atr")    or 0)
        atr_15m      = float(d15m.get("atr")   or 0) if d15m else 0.0

        volatility_regime = _get_volatility_regime(atr_4h, coin_ema20)
        fear_greed        = _get_fear_greed_cached()
        funding_rate      = _get_funding_rate(signal.get("coin", ""))

        perf             = _get_performance_state()
        drawdown         = perf.get("drawdown",    0.0)
        win_rate         = perf.get("win_rate")
        streak           = perf.get("streak",      0)
        streak_type      = perf.get("streak_type")
        daily_pnl        = perf.get("daily_pnl",   0.0)
        open_trades_count= perf.get("open_trades", 0)

        thresholds = {
            "sweep_min_score":       cfg.SCALP_ENGINE.get("sweep_min_score",       0.30),
            "zone_min_score":        cfg.SCALP_ENGINE.get("zone_min_score",        0.40),
            "grade_a_threshold":     cfg.SCALP_ENGINE.get("grade_a_threshold",     0.65),
            "grade_aplus_threshold": cfg.SCALP_ENGINE.get("grade_aplus_threshold", 0.80),
            "sweep_max_age_hours":   cfg.SCALP_ENGINE.get("sweep_max_age_hours",   12),
            "base_risk_pct":         cfg.SCALP_ENGINE.get("base_risk_pct",         0.01),
        }

        sweep_data = signal.get("sweep") or {}
        if isinstance(sweep_data, dict) and "sweep" in sweep_data:
            sweep_data = sweep_data["sweep"] or {}

        zone_data = signal.get("zone") or {}

        with get_session() as db:
            existing = db.query(SignalSnapshot).filter(
                SignalSnapshot.signal_id == signal_id
            ).first()
            if existing:
                return True

            snapshot = SignalSnapshot(
                signal_id            = signal_id,
                system_version       = version,
                coin                 = signal.get("coin", ""),
                direction            = signal.get("direction", ""),
                grade                = signal.get("grade", ""),
                combined_score       = float(signal.get("score", 0)),
                sweep_score          = float(signal.get("sweep_score", 0)),
                zone_score           = float(signal.get("zone_score",  0)),
                trigger_score        = float(signal.get("trigger_score", 0)),
                sweep_age_hours      = float(sweep_data.get("age_hours",  0)),
                sweep_confirmed      = bool(sweep_data.get("confirmed",   False)),
                sweep_intensity      = int(sweep_data.get("intensity",    0)),
                sweep_wick_atr       = float(sweep_data.get("wick_atr",   0)),
                sweep_vol_ratio      = float(sweep_data.get("vol_ratio",  0)),
                sweep_label          = str(sweep_data.get("label",        "")),
                zone_type            = str(zone_data.get("type",          "")),
                zone_touch_count     = int(zone_data.get("touch_count",   0)),
                zone_width_atr       = float(zone_data.get("score",       0)),
                zone_distance_pct    = float(zone_data.get("distance_pct",0)),
                trigger_pattern      = str(signal.get("trigger_pattern",  "")),
                trigger_vol_mult     = float(signal.get("trigger_vol_mult",0)),
                entry_price          = float(signal.get("entry",          0)),
                sl_price             = float(signal.get("sl",             0)),
                tp1_price            = float(signal.get("tp1",            0)),
                sl_pct               = float(signal.get("sl_pct",         0)),
                rr1                  = float(signal.get("rr1",            0)),
                session              = signal.get("session",              ""),
                regime               = signal.get("regime",               ""),
                day_of_week          = day_of_week,
                hour_of_day          = hour_of_day,
                btc_direction        = btc_direction,
                btc_adx              = btc_adx,
                btc_ema_aligned      = btc_aligned,
                coin_adx             = coin_adx,
                coin_ema20           = coin_ema20,
                coin_ema50           = coin_ema50,
                funding_rate         = funding_rate,
                fear_greed_value     = fear_greed,
                volatility_regime    = volatility_regime,
                atr_4h               = atr_4h,
                atr_1h               = atr_1h,
                atr_15m              = atr_15m,
                factor_scores_json   = json.dumps(factor_scores) if factor_scores else None,
                ml_probability       = signal.get("ml_probability"),
                drawdown_at_signal   = drawdown,
                win_rate_at_signal   = win_rate,
                streak_at_signal     = streak,
                streak_type_at_signal= streak_type,
                daily_pnl_at_signal  = daily_pnl,
                open_trades_at_signal= open_trades_count,
                balance_at_signal    = balance,
                thresholds_json      = json.dumps(thresholds),
            )
            db.add(snapshot)

        log.info("Snapshot captured: signal_id=%s coin=%s grade=%s version=%s",
                 signal_id, signal.get("coin"), signal.get("grade"), version)
        return True

    except Exception as e:
        log.error("observer.capture signal_id=%s: %s", signal_id, e)
        return False


def _get_btc_data() -> dict | None:
    try:
        from data.cache import cache
        return cache.get_raw("btc_4h_data")
    except Exception:
        return None


def _get_volatility_regime(atr: float, price: float) -> str:
    if not atr or not price or price == 0:
        return "unknown"
    atr_pct = atr / price * 100
    if atr_pct < 0.5:
        return "low"
    if atr_pct < 1.5:
        return "normal"
    if atr_pct < 3.0:
        return "elevated"
    return "high"


def _get_fear_greed_cached() -> int | None:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return None
        val = r.get("fear_greed_value")
        if val:
            return int(val)
        return None
    except Exception:
        return None


def _get_funding_rate(coin: str) -> float:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return 0.0
        raw = r.get(f"funding:{coin}USDT")
        if raw:
            return float(raw)
        return 0.0
    except Exception:
        return 0.0


def _get_performance_state() -> dict:
    try:
        from database import SessionLocal, Trade as TradeModel
        from datetime import date

        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).order_by(TradeModel.opened_at.desc()).limit(20).all()

            active = db.query(TradeModel).filter(
                TradeModel.is_active == True
            ).count()

            today_start = datetime(
                date.today().year,
                date.today().month,
                date.today().day,
                tzinfo=timezone.utc
            )
            today_trades = db.query(TradeModel).filter(
                TradeModel.closed_at >= today_start,
                TradeModel.outcome.in_(["win", "loss"])
            ).all()

        daily_pnl = sum(float(t.net_pnl or t.pnl or 0) for t in today_trades)

        if not closed:
            return {
                "drawdown":    0.0,
                "win_rate":    None,
                "streak":      0,
                "streak_type": None,
                "daily_pnl":   daily_pnl,
                "open_trades": active,
            }

        wins     = sum(1 for t in closed if t.outcome == "win")
        win_rate = wins / len(closed)

        streak      = 0
        streak_type = None
        for t in closed:
            if streak == 0:
                streak_type = t.outcome
                streak      = 1
            elif t.outcome == streak_type:
                streak += 1
            else:
                break

        all_closed = db.query(TradeModel).filter(
            TradeModel.outcome.in_(["win", "loss"]),
            TradeModel.net_pnl.isnot(None)
        ).order_by(TradeModel.opened_at.asc()).all() if False else []

        try:
            from database import SessionLocal as SL
            with SL() as db2:
                all_closed = db2.query(TradeModel).filter(
                    TradeModel.outcome.in_(["win", "loss"]),
                    TradeModel.net_pnl.isnot(None)
                ).order_by(TradeModel.opened_at.asc()).all()
        except Exception:
            all_closed = []

        equity   = 0.0
        peak     = 0.0
        drawdown = 0.0
        for t in all_closed:
            equity += float(t.net_pnl or t.pnl or 0)
            if equity > peak:
                peak = equity
        if peak > 0:
            drawdown = max(0.0, (peak - equity) / peak)

        return {
            "drawdown":    round(drawdown, 4),
            "win_rate":    round(win_rate, 4),
            "streak":      streak,
            "streak_type": streak_type,
            "daily_pnl":   round(daily_pnl, 4),
            "open_trades": active,
        }

    except Exception as e:
        log.error("_get_performance_state: %s", e)
        return {
            "drawdown":    0.0,
            "win_rate":    None,
            "streak":      0,
            "streak_type": None,
            "daily_pnl":   0.0,
            "open_trades": 0,
        }


def get_snapshot(signal_id: int) -> dict | None:
    try:
        with get_session() as db:
            row = db.query(SignalSnapshot).filter(
                SignalSnapshot.signal_id == signal_id
            ).first()
            if not row:
                return None
            return _row_to_dict(row)
    except Exception as e:
        log.error("get_snapshot: %s", e)
        return None


def get_snapshots_for_analysis(min_trades: int = 50) -> list:
    try:
        from database import SessionLocal, Signal as SignalModel
        with SessionLocal() as db:
            rows = db.query(SignalSnapshot).join(
                SignalModel,
                SignalSnapshot.signal_id == SignalModel.id
            ).filter(
                SignalModel.outcome.in_(["win", "loss"])
            ).all()

        if len(rows) < min_trades:
            return []

        return [_row_to_dict(r) for r in rows]

    except Exception as e:
        log.error("get_snapshots_for_analysis: %s", e)
        return []


def _row_to_dict(row: SignalSnapshot) -> dict:
    return {
        "id":                    row.id,
        "signal_id":             row.signal_id,
        "captured_at":           row.captured_at.isoformat() if row.captured_at else None,
        "system_version":        row.system_version,
        "coin":                  row.coin,
        "direction":             row.direction,
        "grade":                 row.grade,
        "combined_score":        row.combined_score,
        "sweep_score":           row.sweep_score,
        "zone_score":            row.zone_score,
        "trigger_score":         row.trigger_score,
        "sweep_age_hours":       row.sweep_age_hours,
        "sweep_confirmed":       row.sweep_confirmed,
        "sweep_intensity":       row.sweep_intensity,
        "sweep_wick_atr":        row.sweep_wick_atr,
        "sweep_vol_ratio":       row.sweep_vol_ratio,
        "sweep_label":           row.sweep_label,
        "zone_type":             row.zone_type,
        "zone_touch_count":      row.zone_touch_count,
        "zone_width_atr":        row.zone_width_atr,
        "zone_distance_pct":     row.zone_distance_pct,
        "trigger_pattern":       row.trigger_pattern,
        "trigger_vol_mult":      row.trigger_vol_mult,
        "entry_price":           row.entry_price,
        "sl_price":              row.sl_price,
        "tp1_price":             row.tp1_price,
        "sl_pct":                row.sl_pct,
        "rr1":                   row.rr1,
        "session":               row.session,
        "regime":                row.regime,
        "day_of_week":           row.day_of_week,
        "hour_of_day":           row.hour_of_day,
        "btc_direction":         row.btc_direction,
        "btc_adx":               row.btc_adx,
        "btc_ema_aligned":       row.btc_ema_aligned,
        "coin_adx":              row.coin_adx,
        "coin_ema20":            row.coin_ema20,
        "coin_ema50":            row.coin_ema50,
        "funding_rate":          row.funding_rate,
        "fear_greed_value":      row.fear_greed_value,
        "volatility_regime":     row.volatility_regime,
        "atr_4h":                row.atr_4h,
        "atr_1h":                row.atr_1h,
        "atr_15m":               row.atr_15m,
        "factor_scores":         json.loads(row.factor_scores_json) if row.factor_scores_json else {},
        "ml_probability":        row.ml_probability,
        "drawdown_at_signal":    row.drawdown_at_signal,
        "win_rate_at_signal":    row.win_rate_at_signal,
        "streak_at_signal":      row.streak_at_signal,
        "streak_type_at_signal": row.streak_type_at_signal,
        "daily_pnl_at_signal":   row.daily_pnl_at_signal,
        "open_trades_at_signal": row.open_trades_at_signal,
        "balance_at_signal":     row.balance_at_signal,
        "thresholds":            json.loads(row.thresholds_json) if row.thresholds_json else {},
    }