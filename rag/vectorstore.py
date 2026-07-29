import logging
import os
from chromadb import PersistentClient
from chromadb.config import Settings

log = logging.getLogger(__name__)

CHROMA_DIR = "database/chroma"

_client = None
_collections = {}

COLLECTION_TRADES      = "trades"
COLLECTION_SIGNALS     = "signals"
COLLECTION_DAILY       = "daily_summaries"
COLLECTION_COINS       = "coin_performance"
COLLECTION_DOCS        = "documentation"


def get_client() -> PersistentClient:
    global _client
    if _client is not None:
        return _client
    os.makedirs(CHROMA_DIR, exist_ok=True)
    _client = PersistentClient(
        path     = CHROMA_DIR,
        settings = Settings(anonymized_telemetry=False),
    )
    log.info("ChromaDB client initialized at %s", CHROMA_DIR)
    return _client


def get_collection(name: str):
    global _collections
    if name in _collections:
        return _collections[name]
    client = get_client()
    collection = client.get_or_create_collection(
        name     = name,
        metadata = {"hnsw:space": "cosine"},
    )
    _collections[name] = collection
    log.info("Collection ready: %s (count: %s)", name, collection.count())
    return collection


def get_trades_collection():
    return get_collection(COLLECTION_TRADES)


def get_signals_collection():
    return get_collection(COLLECTION_SIGNALS)


def get_daily_collection():
    return get_collection(COLLECTION_DAILY)


def get_coins_collection():
    return get_collection(COLLECTION_COINS)


def get_docs_collection():
    return get_collection(COLLECTION_DOCS)


def get_all_collections() -> dict:
    return {
        COLLECTION_TRADES:  get_trades_collection(),
        COLLECTION_SIGNALS: get_signals_collection(),
        COLLECTION_DAILY:   get_daily_collection(),
        COLLECTION_COINS:   get_coins_collection(),
        COLLECTION_DOCS:    get_docs_collection(),
    }


def get_collection_stats() -> dict:
    stats = {}
    for name in [
        COLLECTION_TRADES,
        COLLECTION_SIGNALS,
        COLLECTION_DAILY,
        COLLECTION_COINS,
        COLLECTION_DOCS,
    ]:
        try:
            col          = get_collection(name)
            stats[name]  = col.count()
        except Exception as e:
            log.error("Stats error for %s: %s", name, e)
            stats[name]  = 0
    return stats


def reset_collection(name: str) -> None:
    client = get_client()
    try:
        client.delete_collection(name)
        log.info("Collection deleted: %s", name)
    except Exception:
        pass
    _collections.pop(name, None)
    get_collection(name)
    log.info("Collection recreated: %s", name)


def reset_all_collections() -> None:
    for name in [
        COLLECTION_TRADES,
        COLLECTION_SIGNALS,
        COLLECTION_DAILY,
        COLLECTION_COINS,
        COLLECTION_DOCS,
    ]:
        reset_collection(name)
    log.info("All collections reset")