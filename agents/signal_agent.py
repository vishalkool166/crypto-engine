import logging
import time
from agents.state import SignalAgentState
from agents.graph import get_signal_graph

log = logging.getLogger(__name__)


def _build_initial_state(
    coin:    str,
    df_4h:   object,
    df_1h:   object,
    df_15m:  object,
    balance: float,
    df_1d:   object = None,
    df_1w:   object = None,
) -> SignalAgentState:
    return SignalAgentState(
        coin            = coin,
        balance         = balance,
        df_4h           = df_4h,
        df_1h           = df_1h,
        df_15m          = df_15m,
        df_1d           = df_1d,
        df_1w           = df_1w,
        direction       = "NEUTRAL",
        atr_4h          = 0.0,
        atr_1h          = 0.0,
        atr_15m         = 0.0,
        d4h             = {},
        d1h             = {},
        d15m            = {},
        regime          = "",
        session         = "",
        ctx             = {},
        sweep_result    = {},
        zone_result     = {},
        trigger_result  = {},
        risk_result     = {},
        sizing_result   = {},
        score           = 0.0,
        grade           = "F",
        ml_probability  = None,
        signal          = True,
        reason          = "",
        trace_steps     = [],
        final_result    = {},
    )


async def run(
    coin:    str,
    df_4h:   object,
    df_1h:   object,
    df_15m:  object,
    balance: float,
    df_1d:   object = None,
    df_1w:   object = None,
) -> dict:
    start = time.time()
    log.info("Signal agent started: %s", coin)

    try:
        graph         = get_signal_graph()
        initial_state = _build_initial_state(
            coin    = coin,
            df_4h   = df_4h,
            df_1h   = df_1h,
            df_15m  = df_15m,
            balance = balance,
            df_1d   = df_1d,
            df_1w   = df_1w,
        )

        final_state = await graph.ainvoke(initial_state)

        elapsed = round((time.time() - start) * 1000, 1)

        result = final_state.get("final_result", {})

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
            "Signal agent complete: %s signal:%s grade:%s reason:%s elapsed:%sms",
            coin,
            result.get("signal",    False),
            result.get("grade",     "F"),
            result.get("reason",    ""),
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


def run_sync(
    coin:    str,
    df_4h:   object,
    df_1h:   object,
    df_15m:  object,
    balance: float,
    df_1d:   object = None,
    df_1w:   object = None,
) -> dict:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    run(coin, df_4h, df_1h, df_15m, balance, df_1d, df_1w)
                )
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(
                run(coin, df_4h, df_1h, df_15m, balance, df_1d, df_1w)
            )
    except Exception as e:
        log.error("run_sync error %s: %s", coin, e)
        return {
            "signal":    False,
            "coin":      coin,
            "direction": "NEUTRAL",
            "grade":     "F",
            "score":     0,
            "reason":    str(e),
        }


def get_trace_summary(result: dict) -> list[dict]:
    trace = result.get("trace", {})
    if not trace:
        return []
    return trace.get("steps", [])


def format_trace_for_telegram(result: dict) -> str:
    steps = get_trace_summary(result)
    if not steps:
        return "No trace available"

    lines = [f"Agent Trace — {result.get('coin', '--')}"]

    for step in steps:
        node   = step.get("node",   "--")
        passed = step.get("passed", False)
        icon   = "✅" if passed else "❌"
        reason = step.get("reason", "")

        line = f"{icon} {node.upper()}"

        if node == "context":
            line += f" → {step.get('direction', '--')}"
        elif node == "sweep":
            line += f" → score:{step.get('score', 0):.3f}"
        elif node == "zone":
            line += f" → {step.get('zone_type', '--')} score:{step.get('score', 0):.3f}"
        elif node == "trigger":
            line += f" → {step.get('pattern', '--')} score:{step.get('score', 0):.3f}"
        elif node == "risk":
            line += f" → rr:{step.get('rr1', 0):.2f}"
        elif node == "grade":
            line += f" → {step.get('grade', '--')} {step.get('score', 0):.1f}%"
        elif node == "ml":
            prob = step.get("probability")
            line += f" → {f'{prob:.3f}' if prob is not None else 'skipped'}"
        elif node == "finalize":
            line += f" → stake:${step.get('stake', 0):.2f} x{step.get('leverage', 0)}"

        if reason and not passed:
            line += f" ({reason})"

        lines.append(line)

    return "\n".join(lines)