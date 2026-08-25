import logging
import os

log = logging.getLogger(__name__)

_langsmith_enabled = False


def start_langsmith() -> bool:
    tracing = os.getenv("LANGCHAIN_TRACING_V2", "false").lower()
    if tracing != "true":
        log.info("LangSmith tracing disabled")
        return False

    api_key = os.getenv("LANGCHAIN_API_KEY", "")
    if not api_key:
        log.info("LangSmith: no API key — tracing disabled")
        return False

    global _langsmith_enabled
    try:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"]    = api_key
        os.environ["LANGCHAIN_PROJECT"]    = os.getenv("LANGCHAIN_PROJECT", "signal-engine-v5")
        os.environ["LANGCHAIN_ENDPOINT"]   = "https://api.smith.langchain.com"

        from langsmith import Client
        client = Client()
        client.list_projects()

        _langsmith_enabled = True
        log.info("LangSmith tracing enabled — project: %s", os.getenv("LANGCHAIN_PROJECT"))
        return True

    except Exception as e:
        log.warning("LangSmith setup error: %s — continuing without tracing", e)
        _langsmith_enabled = False
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
        "enabled":     _langsmith_enabled,
        "project":     project,
        "url":         get_langsmith_url(),
        "api_key_set": bool(api_key),
        "dashboard":   "https://smith.langchain.com",
    }


def stop_langsmith() -> None:
    global _langsmith_enabled
    _langsmith_enabled = False
    log.info("LangSmith tracing stopped")