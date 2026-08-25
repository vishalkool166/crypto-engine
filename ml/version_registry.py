import json
import logging
from datetime import datetime, timezone
from database import get_session, SystemVersion
from config import cfg

log = logging.getLogger(__name__)


def _get_current_parameters() -> dict:
    HE = cfg.HYBRID_ENGINE
    return {
        "sweep_min_score":       HE.get("sweep_min_score",       0.45),
        "zone_min_score":        HE.get("zone_min_score",        0.45),
        "ict_min_score":         HE.get("ict_min_score",         55),
        "grade_aplus":           HE.get("grade_aplus",           85),
        "grade_a":               HE.get("grade_a",               68),
        "grade_b":               HE.get("grade_b",               52),
        "sweep_max_age_hours":   HE.get("sweep_max_age_hours",   24),
        "sweep_min_wick_atr":    HE.get("sweep_min_wick_atr",    1.5),
        "zone_min_width_atr":    HE.get("zone_min_width_atr",    0.15),
        "zone_max_dist_pct":     HE.get("zone_max_dist_pct",     1.0),
        "zone_max_touches":      HE.get("zone_max_touches",      2),
        "trigger_min_score":     HE.get("trigger_min_score",     0.75),
        "base_risk_pct":         HE.get("base_risk_pct",         0.01),
        "max_risk_pct":          HE.get("max_risk_pct",          0.02),
        "min_risk_pct":          HE.get("min_risk_pct",          0.005),
        "daily_loss_limit_pct":  HE.get("daily_loss_limit_pct",  0.02),
        "max_open_trades":       HE.get("max_open_trades",       2),
        "max_leverage":          HE.get("max_leverage",          10),
        "tp1_min_rr":            HE.get("tp1_min_rr",            2.0),
        "tp2_min_rr":            HE.get("tp2_min_rr",            3.5),
        "regime_adx_trending":   HE.get("regime_adx_trending",  25),
        "regime_adx_ranging":    HE.get("regime_adx_ranging",   15),
        "reversion_rsi_long_max":HE.get("reversion_rsi_long_max", 52),
        "ml_threshold":          HE.get("ml_threshold",          0.50),
        "ml_enabled":            cfg.ML_ENABLED,
        "trading_mode":          cfg.TRADING_MODE,
        "adaptation_frozen":     cfg.ADAPTATION_FROZEN,
    }


def get_current_version() -> str:
    return cfg.SYSTEM_VERSION


def get_current_version_record() -> dict | None:
    try:
        with get_session() as db:
            row = db.query(SystemVersion).filter(
                SystemVersion.is_current == True
            ).order_by(SystemVersion.created_at.desc()).first()
            if not row:
                return None
            return {
                "version":        row.version,
                "created_at":     row.created_at.isoformat() if row.created_at else None,
                "parameters":     json.loads(row.parameters_json),
                "change_reason":  row.change_reason,
                "changed_by":     row.changed_by,
                "trade_count_at": row.trade_count_at,
            }
    except Exception as e:
        log.error("get_current_version_record: %s", e)
        return None


def ensure_version_exists() -> str:
    version = get_current_version()
    try:
        with get_session() as db:
            existing = db.query(SystemVersion).filter(
                SystemVersion.version == version
            ).first()
            if existing:
                return version
            params = _get_current_parameters()
            row    = SystemVersion(
                version         = version,
                parameters_json = json.dumps(params),
                change_reason   = "Initial version",
                changed_by      = "system",
                trade_count_at  = _get_total_trades(),
                is_current      = True,
            )
            db.add(row)
            log.info("Version registered: %s", version)
            return version
    except Exception as e:
        log.error("ensure_version_exists: %s", e)
        return version


def create_new_version(
    reason:     str,
    changed_by: str = "system",
) -> str:
    try:
        current = get_current_version()
        parts   = current.split(".")
        if len(parts) == 3:
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
            patch  += 1
            if patch >= 100:
                patch  = 0
                minor += 1
            if minor >= 100:
                minor  = 0
                major += 1
            new_version = f"{major}.{minor}.{patch}"
        else:
            new_version = current + ".1"

        params = _get_current_parameters()

        with get_session() as db:
            db.query(SystemVersion).filter(
                SystemVersion.is_current == True
            ).update({"is_current": False})

            row = SystemVersion(
                version         = new_version,
                parameters_json = json.dumps(params),
                change_reason   = reason,
                changed_by      = changed_by,
                trade_count_at  = _get_total_trades(),
                is_current      = True,
            )
            db.add(row)

        cfg.update_system_version(new_version)
        log.info("New version created: %s — %s", new_version, reason)
        return new_version

    except Exception as e:
        log.error("create_new_version: %s", e)
        return get_current_version()


def restore_version(version: str, reason: str = "manual_rollback") -> bool:
    try:
        with get_session() as db:
            target = db.query(SystemVersion).filter(
                SystemVersion.version == version
            ).first()
            if not target:
                log.error("Version not found: %s", version)
                return False

            params = json.loads(target.parameters_json)
            HE     = cfg.HYBRID_ENGINE

            for key, value in params.items():
                if key in HE:
                    HE[key] = value
                elif key == "ml_enabled":
                    cfg.ML_ENABLED = bool(value)

            db.query(SystemVersion).filter(
                SystemVersion.is_current == True
            ).update({"is_current": False})

            new_version = version + "_restored"
            row = SystemVersion(
                version         = new_version,
                parameters_json = json.dumps(params),
                change_reason   = f"{reason} — restored from {version}",
                changed_by      = "system",
                trade_count_at  = _get_total_trades(),
                is_current      = True,
            )
            db.add(row)

        cfg.update_system_version(new_version)
        log.info("Version restored: %s → %s", version, new_version)
        return True

    except Exception as e:
        log.error("restore_version: %s", e)
        return False


def get_version_history(limit: int = 20) -> list:
    try:
        with get_session() as db:
            rows = db.query(SystemVersion).order_by(
                SystemVersion.created_at.desc()
            ).limit(limit).all()
            return [{
                "version":        r.version,
                "created_at":     r.created_at.isoformat() if r.created_at else None,
                "parameters":     json.loads(r.parameters_json),
                "change_reason":  r.change_reason,
                "changed_by":     r.changed_by,
                "trade_count_at": r.trade_count_at,
                "is_current":     r.is_current,
            } for r in rows]
    except Exception as e:
        log.error("get_version_history: %s", e)
        return []


def get_version_parameters(version: str) -> dict | None:
    try:
        with get_session() as db:
            row = db.query(SystemVersion).filter(
                SystemVersion.version == version
            ).first()
            if not row:
                return None
            return json.loads(row.parameters_json)
    except Exception as e:
        log.error("get_version_parameters: %s", e)
        return None


def tag_signal(signal_id: int) -> str:
    version = ensure_version_exists()
    try:
        from database import SessionLocal, Signal as SignalModel
        with SessionLocal() as db:
            sig = db.query(SignalModel).filter(SignalModel.id == signal_id).first()
            if sig:
                sig.system_version = version
        return version
    except Exception as e:
        log.error("tag_signal %s: %s", signal_id, e)
        return version


def tag_trade(trade_id: int) -> str:
    version = ensure_version_exists()
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if trade:
                trade.system_version = version
        return version
    except Exception as e:
        log.error("tag_trade %s: %s", trade_id, e)
        return version


def _get_total_trades() -> int:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            return db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).count()
    except Exception:
        return 0


def get_performance_by_version() -> list:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            trades = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"]),
                TradeModel.system_version.isnot(None)
            ).all()

        by_version: dict = {}
        for t in trades:
            v = t.system_version
            if v not in by_version:
                by_version[v] = {"wins": 0, "losses": 0, "pnl": 0.0}
            by_version[v]["pnl"] += float(t.net_pnl or t.pnl or 0)
            if t.outcome == "win":
                by_version[v]["wins"] += 1
            else:
                by_version[v]["losses"] += 1

        result = []
        for version, stats in by_version.items():
            total = stats["wins"] + stats["losses"]
            result.append({
                "version":  version,
                "total":    total,
                "wins":     stats["wins"],
                "losses":   stats["losses"],
                "win_rate": round(stats["wins"] / total * 100, 1) if total > 0 else 0,
                "pnl":      round(stats["pnl"], 4),
            })

        result.sort(key=lambda x: x["version"])
        return result

    except Exception as e:
        log.error("get_performance_by_version: %s", e)
        return []