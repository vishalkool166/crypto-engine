import logging
import time
from agents.state import SignalAgentState
from agents.graph import get_signal_graph

log = logging.getLogger(__name__)


def _build_initial_state(
    coin:    str,
    df_4h:   object,
    df_1h:   object,
    balance: float,
) -> SignalAgentState:
    return SignalAgentState(
        coin          = coin,
        balance       = balance,
        df_4h         = df_4h,
        df_1h         = df_1h,
        d4h           = {},
        d1h           = {},
        atr_4h        = 0.0,
        atr_1h        = 0.0,
        regime_result = None,
        trend_result  = None,
        risk_result   = None,
        sizing_result = None,
        direction     = "NEUTRAL",
        regime_label  = "",
        regime_mult   = 1.0,
        session       = "",
        score         = 0.0,
        grade         = "F",
        signal        = True,
        reason        = "",
        trace_steps   = [],
        final_result  = {},
    )


async def run(
    coin:    str,
    df_4h:   object,
    df_1h:   object,
    balance: float,
) -> dict:
    start = time.time()
    log.info("Signal agent started: %s", coin)

    try:
        graph         = get_signal_graph()
        initial_state = _build_initial_state(
            coin    = coin,
            df_4h   = df_4h,
            df_1h   = df_1h,
            balance = balance,
        )

        final_state = await graph.ainvoke(initial_state)
        elapsed     = round((time.time() - start) * 1000, 1)
        result      = final_state.get("final_result", {})

        if not result:
            result = {
                "signal":    False,
                "coin":      coin,
                "direction": "NEUTRAL",
                "grade":     "F",
                "score":     0,
                "reason":    "no_final_result",
            }

        result["agent_ms"]    = elapsed
        result["agent_steps"] = len(final_state.get("trace_steps", []))

        log.info(
            "Signal agent complete: %s signal:%s grade:%s elapsed:%sms",
            coin,
            result.get("signal",  False),
            result.get("grade",   "F"),
            elapsed,
        )

        return result

    except Exception as e:
        elapsed = round((time.time() - start) * 1000, 1)
        log.error("Signal agent error %s: %s", coin, e, exc_info=True)
        return {
            "signal":     False,
            "coin":       coin,
            "direction":  "NEUTRAL",
            "grade":      "F",
            "score":      0,
            "reason":     str(e),
            "agent_ms":   elapsed,
            "agent_steps":0,
        }