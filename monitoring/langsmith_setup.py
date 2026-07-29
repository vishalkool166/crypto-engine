import logging
import os

log = logging.getLogger(__name__)

_langsmith_enabled = False


def start_langsmith() -> bool:
    global _langsmith_enabled

    try:
        api_key  = os.getenv("LANGCHAIN_API_KEY", "")
        project  = os.getenv("LANGCHAIN_PROJECT", "signal-engine-v5")
        tracing  = os.getenv("LANGCHAIN_TRACING_V2", "false").lower()

        if not api_key:
            log.warning("LangSmith: LANGCHAIN_API_KEY not set — tracing disabled")
            return False

        if tracing != "true":
            log.warning("LangSmith: LANGCHAIN_TRACING_V2 not true — tracing disabled")
            return False

        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"]    = api_key
        os.environ["LANGCHAIN_PROJECT"]    = project
        os.environ["LANGCHAIN_ENDPOINT"]   = "https://api.smith.langchain.com"

        from langsmith import Client
        client = Client()
        client.list_projects()

        _langsmith_enabled = True

        log.info(
            "LangSmith tracing enabled — project: %s — dashboard: https://smith.langchain.com",
            project
        )
        return True

    except Exception as e:
        log.error("LangSmith setup error: %s", e)
        return False


def is_langsmith_enabled() -> bool:
    return _langsmith_enabled


def get_langsmith_url() -> str:
    project = os.getenv("LANGCHAIN_PROJECT", "signal-engine-v5")
    return f"https://smith.langchain.com/projects/{project}"


def get_langsmith_status() -> dict:
    project = os.getenv("LANGCHAIN_PROJECT", "signal-engine-v5")
    api_key = os.getenv("LANGCHAIN_API_KEY", "")
    return {
        "enabled":   _langsmith_enabled,
        "project":   project,
        "url":       get_langsmith_url(),
        "api_key_set": bool(api_key),
        "dashboard": "https://smith.langchain.com",
    }


def stop_langsmith() -> None:
    global _langsmith_enabled
    _langsmith_enabled = False
    log.info("LangSmith tracing stopped")