import logging
from config import cfg

log = logging.getLogger(__name__)


def _is_rag_ready() -> bool:
    try:
        from rag.vectorstore import get_collection_stats
        stats = get_collection_stats()
        total = sum(stats.values())
        return total > 0
    except Exception:
        return False


def _is_off_topic(message: str) -> bool:
    off_topic_keywords = [
        "recipe", "weather", "movie", "sport", "football",
        "cricket", "politics", "news", "celebrity", "music",
        "game", "joke", "poem", "story", "write code for",
        "help me with my homework", "translate",
    ]
    m = message.lower()
    return any(k in m for k in off_topic_keywords)


async def chat(user_message: str) -> str:
    if not cfg.GROQ_API_KEY:
        return "AI assistant not configured. Add GROQ_API_KEY to .env and restart."

    if _is_off_topic(user_message):
        return "I only answer questions about your Signal Engine trading data and performance."

    try:
        if _is_rag_ready():
            from rag.chain import ask_with_fallback
            result = await ask_with_fallback(user_message)
            return result.get("answer", "Could not generate answer.")
        else:
            log.warning("RAG not ready — using basic chatbot")
            from chatbot import chat as basic_chat
            return await basic_chat(user_message)

    except Exception as e:
        log.error("chatbot_rag error: %s", e)
        try:
            from chatbot import chat as basic_chat
            return await basic_chat(user_message)
        except Exception as e2:
            log.error("Basic chatbot fallback failed: %s", e2)
            return "AI assistant temporarily unavailable. Try again shortly."


async def chat_with_sources(user_message: str) -> dict:
    if not cfg.GROQ_API_KEY:
        return {
            "answer":   "AI assistant not configured.",
            "sources":  [],
            "chunks":   0,
            "rag_used": False,
        }

    if _is_off_topic(user_message):
        return {
            "answer":   "I only answer questions about your Signal Engine trading data.",
            "sources":  [],
            "chunks":   0,
            "rag_used": False,
        }

    try:
        if _is_rag_ready():
            from rag.chain import ask_with_fallback
            result  = await ask_with_fallback(user_message)
            rag_used= not result.get("fallback", False)
            return {
                "answer":   result.get("answer",  ""),
                "sources":  result.get("sources", []),
                "chunks":   result.get("chunks",  0),
                "rag_used": rag_used,
            }
        else:
            from chatbot import chat as basic_chat
            answer = await basic_chat(user_message)
            return {
                "answer":   answer,
                "sources":  [],
                "chunks":   0,
                "rag_used": False,
            }

    except Exception as e:
        log.error("chat_with_sources error: %s", e)
        return {
            "answer":   "AI assistant temporarily unavailable.",
            "sources":  [],
            "chunks":   0,
            "rag_used": False,
        }


def get_rag_status() -> dict:
    try:
        from rag.vectorstore import get_collection_stats
        stats    = get_collection_stats()
        total    = sum(stats.values())
        is_ready = total > 0
        return {
            "rag_ready":   is_ready,
            "total_chunks":total,
            "collections": stats,
            "groq_ready":  bool(cfg.GROQ_API_KEY),
        }
    except Exception as e:
        log.error("get_rag_status error: %s", e)
        return {
            "rag_ready":   False,
            "total_chunks":0,
            "collections": {},
            "groq_ready":  bool(cfg.GROQ_API_KEY),
        }