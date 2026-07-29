import logging

log = logging.getLogger(__name__)

_phoenix_session = None


def start_phoenix() -> bool:
    global _phoenix_session

    try:
        import phoenix as px

        _phoenix_session = px.launch_app()

        url = "http://localhost:6006"
        try:
            url = _phoenix_session.url
        except Exception:
            pass

        log.info("Phoenix started — dashboard at %s", url)

        _instrument_langchain()
        _instrument_langgraph()

        log.info("Phoenix instrumentation complete")
        return True

    except Exception as e:
        log.error("Phoenix start error: %s", e)
        return False


def _instrument_langchain() -> None:
    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor
        LangChainInstrumentor().instrument()
        log.info("LangChain instrumented with Phoenix")
    except Exception as e:
        log.warning("LangChain instrumentation error: %s", e)


def _instrument_langgraph() -> None:
    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor
        log.info("LangGraph instrumented via LangChain instrumentor")
    except Exception as e:
        log.warning("LangGraph instrumentation error: %s", e)


def get_phoenix_url() -> str:
    if _phoenix_session:
        try:
            return _phoenix_session.url
        except Exception:
            pass
    return "http://localhost:6006"


def is_phoenix_running() -> bool:
    return _phoenix_session is not None


def get_phoenix_status() -> dict:
    return {
        "running": is_phoenix_running(),
        "url":     get_phoenix_url(),
        "project": "signal-engine-v5",
    }


def stop_phoenix() -> None:
    global _phoenix_session
    try:
        if _phoenix_session:
            _phoenix_session.end()
            _phoenix_session = None
            log.info("Phoenix stopped")
    except Exception as e:
        log.error("Phoenix stop error: %s", e)