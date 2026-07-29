import logging
from agents.state import SignalAgentState
from config import cfg

log = logging.getLogger(__name__)


def _get_total_trades() -> int:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            return db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).count()
    except Exception:
        return 0


def ml_node(state: SignalAgentState) -> SignalAgentState:
    coin           = state["coin"]
    direction      = state["direction"]
    grade          = state["grade"]
    score          = state["score"]
    sweep_result   = state["sweep_result"]
    zone_result    = state["zone_result"]
    trigger_result = state["trigger_result"]

    try:
        total_trades = _get_total_trades()

        if not cfg.ML_ENABLED or total_trades < cfg.ML_MIN_TRADES:
            state["ml_probability"] = None
            state["trace_steps"].append({
                "node":          "ml",
                "passed":        True,
                "ml_enabled":    cfg.ML_ENABLED,
                "total_trades":  total_trades,
                "min_trades":    cfg.ML_MIN_TRADES,
                "probability":   None,
                "reason":        "ml_not_active_yet" if not cfg.ML_ENABLED else "insufficient_trades",
            })
            log.debug(
                "ml_node %s — skipped (enabled:%s trades:%s/%s)",
                coin, cfg.ML_ENABLED, total_trades, cfg.ML_MIN_TRADES
            )
            return state

        signal_dict = {
            "coin":          coin,
            "direction":     direction,
            "sweep_score":   sweep_result.get("score",   0),
            "zone_score":    zone_result.get("score",    0),
            "trigger_score": trigger_result.get("score", 0),
            "grade":         grade,
            "score":         score,
            "funding":       0,
        }

        wconf = {
            "factors":      [],
            "market_score": round(sweep_result.get("score",   0) * 100, 2),
            "entry_score":  round(trigger_result.get("score", 0) * 100, 2),
            "btc_score":    6.0,
        }

        from ml.predictor import predict_win_probability
        probability = predict_win_probability(signal_dict, wconf)
        state["ml_probability"] = probability

        threshold = cfg.SCALP_ENGINE.get("ml_threshold", 0.65)
        passed    = probability >= threshold

        step = {
            "node":        "ml",
            "passed":      passed,
            "probability": probability,
            "threshold":   threshold,
            "total_trades":total_trades,
            "reason":      "" if passed else f"ml_blocked:{probability:.3f}<{threshold}",
        }
        state["trace_steps"].append(step)

        if not passed:
            state["signal"] = False
            state["reason"] = f"ml_gate_blocked:{probability:.3f}"

        log.debug(
            "ml_node %s — passed:%s probability:%.3f threshold:%.3f",
            coin, passed, probability, threshold
        )

    except Exception as e:
        log.error("ml_node %s: %s", coin, e)
        state["ml_probability"] = None
        state["trace_steps"].append({
            "node":   "ml",
            "passed": True,
            "reason": f"ml_node_error_passthrough: {e}",
        })

    return state