import logging
from sentence_transformers import SentenceTransformer
from rag.vectorstore import (
    get_trades_collection,
    get_signals_collection,
    get_daily_collection,
    get_coins_collection,
    get_docs_collection,
)

log = logging.getLogger(__name__)

_embedder = None


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is not None:
        return _embedder
    from rag.indexer import get_embedder as _get
    _embedder = _get()
    return _embedder


def _embed_query(query: str) -> list[float]:
    embedder = get_embedder()
    return embedder.encode(query, show_progress_bar=False).tolist()


def _detect_intent(query: str) -> list[str]:
    q = query.lower()

    collections = []

    trade_keywords = [
        "trade", "loss", "win", "fail", "profit", "pnl",
        "closed", "opened", "position", "outcome", "result",
        "when do i", "why did", "how did", "stop loss",
        "take profit", "sl hit", "tp hit", "duration",
    ]

    signal_keywords = [
        "signal", "grade", "score", "sweep", "zone",
        "displacement", "confluence", "factor", "a+", "grade a",
        "why signal", "what signal", "best signal", "worst signal",
        "btc score", "market score", "entry score",
    ]

    daily_keywords = [
        "today", "yesterday", "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday", "sunday", "week",
        "daily", "this week", "last week", "day", "date",
        "session", "period",
    ]

    coin_keywords = [
        "btc", "eth", "sol", "bnb", "coin", "which coin",
        "best coin", "worst coin", "performance", "how do i do on",
        "most profitable", "least profitable",
    ]

    doc_keywords = [
        "what is", "explain", "how does", "what does",
        "order block", "fvg", "sweep", "ict", "regime",
        "session", "confluence", "grade mean", "score mean",
        "how it works", "what are", "define",
    ]

    if any(k in q for k in trade_keywords):
        collections.append("trades")

    if any(k in q for k in signal_keywords):
        collections.append("signals")

    if any(k in q for k in daily_keywords):
        collections.append("daily")

    if any(k in q for k in coin_keywords):
        collections.append("coins")

    if any(k in q for k in doc_keywords):
        collections.append("docs")

    if not collections:
        collections = ["trades", "signals", "coins"]

    return list(dict.fromkeys(collections))


def retrieve(
    query:       str,
    n_results:   int  = 5,
    collections: list = None,
) -> list[dict]:
    if collections is None:
        collections = _detect_intent(query)

    log.debug("Retrieving for query: '%s' from collections: %s", query, collections)

    query_embedding = _embed_query(query)

    collection_map = {
        "trades":  get_trades_collection,
        "signals": get_signals_collection,
        "daily":   get_daily_collection,
        "coins":   get_coins_collection,
        "docs":    get_docs_collection,
    }

    all_results = []

    for col_name in collections:
        if col_name not in collection_map:
            continue

        try:
            collection = collection_map[col_name]()

            if collection.count() == 0:
                log.debug("Collection %s is empty — skipping", col_name)
                continue

            per_col = max(2, n_results // len(collections))

            results = collection.query(
                query_embeddings = [query_embedding],
                n_results        = min(per_col, collection.count()),
                include          = ["documents", "metadatas", "distances"],
            )

            docs      = results.get("documents",  [[]])[0]
            metas     = results.get("metadatas",  [[]])[0]
            distances = results.get("distances",  [[]])[0]

            for doc, meta, dist in zip(docs, metas, distances):
                similarity = round(1 - dist, 4)
                if similarity < 0.2:
                    continue
                all_results.append({
                    "content":    doc,
                    "metadata":   meta,
                    "similarity": similarity,
                    "collection": col_name,
                })

        except Exception as e:
            log.error("Retrieval error from %s: %s", col_name, e)

    all_results.sort(key=lambda x: x["similarity"], reverse=True)
    top_results = all_results[:n_results]

    log.debug(
        "Retrieved %s chunks from %s collections",
        len(top_results), len(collections)
    )

    return top_results


def retrieve_trades_only(query: str, n_results: int = 5) -> list[dict]:
    return retrieve(query, n_results=n_results, collections=["trades"])


def retrieve_signals_only(query: str, n_results: int = 5) -> list[dict]:
    return retrieve(query, n_results=n_results, collections=["signals"])


def retrieve_for_coin(query: str, coin: str, n_results: int = 5) -> list[dict]:
    query_embedding = _embed_query(f"{coin} {query}")
    results         = []

    for get_col in [get_trades_collection, get_signals_collection]:
        try:
            collection = get_col()
            if collection.count() == 0:
                continue

            raw = collection.query(
                query_embeddings = [query_embedding],
                n_results        = min(n_results, collection.count()),
                where            = {"coin": coin.upper()},
                include          = ["documents", "metadatas", "distances"],
            )

            docs      = raw.get("documents",  [[]])[0]
            metas     = raw.get("metadatas",  [[]])[0]
            distances = raw.get("distances",  [[]])[0]

            for doc, meta, dist in zip(docs, metas, distances):
                similarity = round(1 - dist, 4)
                results.append({
                    "content":    doc,
                    "metadata":   meta,
                    "similarity": similarity,
                    "collection": "coin_filtered",
                })

        except Exception as e:
            log.error("retrieve_for_coin error %s: %s", coin, e)

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:n_results]


def format_retrieved_context(results: list[dict]) -> str:
    if not results:
        return "No relevant data found in trading history."

    lines = ["RELEVANT TRADING DATA:\n"]

    for i, r in enumerate(results, 1):
        col   = r.get("collection", "")
        sim   = r.get("similarity", 0)
        lines.append(f"[{i}] Source: {col} | Relevance: {sim:.2f}")
        lines.append(r["content"])
        lines.append("")

    return "\n".join(lines)


def get_retriever_stats() -> dict:
    from rag.vectorstore import get_collection_stats
    return {
        "collection_counts": get_collection_stats(),
    }