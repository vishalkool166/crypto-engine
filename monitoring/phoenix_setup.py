import logging
import os

log = logging.getLogger(__name__)

_phoenix_session = None
_tracer_provider = None


def start_phoenix() -> bool:
    global _phoenix_session, _tracer_provider

    try:
        import phoenix as px

        _phoenix_session = px.launch_app()

        url = "http://localhost:6006"
        try:
            url = _phoenix_session.url
        except Exception:
            pass

        log.info("Phoenix started — dashboard at %s", url)

        try:
            from phoenix.otel import register
            _tracer_provider = register(
                project_name    = "signal-engine-v5",
                auto_instrument = True,
            )
            log.info("Phoenix OTEL registered")
        except Exception as e:
            log.warning("Phoenix OTEL registration failed: %s", e)

        _instrument_langchain()

        log.info("Phoenix instrumentation complete")
        return True

    except Exception as e:
        log.error("Phoenix start error: %s", e)
        return False


def _instrument_langchain() -> None:
    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor
        if _tracer_provider:
            LangChainInstrumentor().instrument(tracer_provider=_tracer_provider)
        else:
            LangChainInstrumentor().instrument()
        log.info("LangChain instrumented with Phoenix")
    except ImportError:
        log.warning("openinference-instrumentation-langchain not installed — skipping")
    except Exception as e:
        log.warning("LangChain instrumentation error: %s", e)


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