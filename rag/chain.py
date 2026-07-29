import logging
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from rag.retriever import retrieve, format_retrieved_context
from config import cfg

log = logging.getLogger(__name__)

_llm = None


def get_llm() -> ChatGroq:
    global _llm
    if _llm is not None:
        return _llm
    _llm = ChatGroq(
        api_key      = cfg.GROQ_API_KEY,
        model        = "llama-3.3-70b-versatile",
        temperature  = 0.3,
        max_tokens   = 500,
    )
    log.info("ChatGroq LLM initialized for RAG chain")
    return _llm


SYSTEM_PROMPT = """You are a trading assistant for Signal Engine v5, an automated crypto futures trading system.

You have access to the user's actual trading data including closed trades, signals, daily summaries, and coin performance.

RULES:
- ONLY answer questions about Signal Engine v5 and its trading data
- ALWAYS use the provided trading data to give specific answers
- ALWAYS mention actual numbers, dates, coins from the data
- If the data does not contain enough information say so clearly
- Never make up trades or statistics that are not in the provided data
- Keep answers concise — 3 to 6 sentences unless more detail is asked
- Refuse all off-topic questions politely

TRADING CONCEPTS YOU KNOW:
- LONG means betting price goes up, SHORT means betting price goes down
- SL is stop loss — price where trade exits to limit loss
- TP is take profit — price where trade locks in gains
- Grade A+ and A are strong signals, B is moderate, C and F are weak
- Confluence score out of 100 measures how many conditions align
- Regime is overall market condition — trending, ranging, or choppy
- Sweep means smart money hunted stop losses before real move
- Session refers to London, New York, Asia, or London/NY Overlap trading hours
- ICT concepts include order blocks, fair value gaps, displacement
- Win rate is percentage of winning trades out of total closed trades"""


RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{context}\n\nUSER QUESTION: {question}"),
])


def _retrieve_and_format(question: str) -> str:
    try:
        results = retrieve(question, n_results=6)
        return format_retrieved_context(results)
    except Exception as e:
        log.error("Retrieval error in chain: %s", e)
        return "Trading data temporarily unavailable."


def build_rag_chain():
    llm    = get_llm()
    parser = StrOutputParser()

    chain = (
        {
            "context":  RunnableLambda(lambda x: _retrieve_and_format(x["question"])),
            "question": RunnablePassthrough() | RunnableLambda(lambda x: x["question"]),
        }
        | RAG_PROMPT
        | llm
        | parser
    )

    return chain


_rag_chain = None


def get_rag_chain():
    global _rag_chain
    if _rag_chain is not None:
        return _rag_chain
    _rag_chain = build_rag_chain()
    log.info("RAG chain built")
    return _rag_chain


async def ask(question: str) -> dict:
    try:
        chain   = get_rag_chain()
        results = retrieve(question, n_results=6)
        context = format_retrieved_context(results)

        answer = await chain.ainvoke({
            "question": question,
            "context":  context,
        })

        sources = []
        for r in results:
            meta = r.get("metadata", {})
            sources.append({
                "type":       meta.get("type",       r.get("collection", "")),
                "coin":       meta.get("coin",        ""),
                "similarity": r.get("similarity",     0),
                "collection": r.get("collection",     ""),
            })

        return {
            "answer":   answer.strip(),
            "sources":  sources,
            "chunks":   len(results),
            "question": question,
        }

    except Exception as e:
        log.error("RAG chain ask error: %s", e)
        return {
            "answer":   "I encountered an error retrieving your trading data. Please try again.",
            "sources":  [],
            "chunks":   0,
            "question": question,
        }


async def ask_with_fallback(question: str) -> dict:
    try:
        from rag.vectorstore import get_collection_stats
        stats = get_collection_stats()
        total = sum(stats.values())

        if total == 0:
            log.warning("Vector store is empty — falling back to basic chatbot")
            from chatbot import chat
            answer = await chat(question)
            return {
                "answer":   answer,
                "sources":  [],
                "chunks":   0,
                "question": question,
                "fallback": True,
            }

        result = await ask(question)
        result["fallback"] = False
        return result

    except Exception as e:
        log.error("ask_with_fallback error: %s", e)
        try:
            from chatbot import chat
            answer = await chat(question)
            return {
                "answer":   answer,
                "sources":  [],
                "chunks":   0,
                "question": question,
                "fallback": True,
            }
        except Exception as e2:
            log.error("Fallback chatbot also failed: %s", e2)
            return {
                "answer":   "AI assistant temporarily unavailable.",
                "sources":  [],
                "chunks":   0,
                "question": question,
                "fallback": True,
            }