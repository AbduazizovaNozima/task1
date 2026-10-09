from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from psycopg_pool import ConnectionPool
from qdrant_client import QdrantClient

from app.adapters.bge_embedder import BgeEmbedder
from app.adapters.pg_chat_history import PostgresChatHistory
from app.adapters.pg_repository import PostgresRepository
from app.adapters.qdrant_index import QdrantIndex
from app.config import Settings
from app.services.conversation import ConversationService
from app.services.ingestion import IngestionService
from app.services.search import SearchService

WARM_UP_TEXT = "salom"


@dataclass(frozen=True)
class Container:
    search: SearchService
    conversation: ConversationService
    ingestion: IngestionService
    check: Callable[[], None]
    warm_up: Callable[[], None]
    close: Callable[[], None]


def build_container(settings: Settings) -> Container:
    pool = ConnectionPool(
        settings.database_url,
        max_size=settings.database_pool_size,
        timeout=settings.database_timeout_seconds,
        open=True,
    )
    repository = PostgresRepository(pool)
    history = PostgresChatHistory(pool, ttl=timedelta(minutes=settings.chat_context_minutes))
    qdrant = QdrantClient(url=settings.qdrant_url, timeout=settings.qdrant_timeout_seconds)
    index = QdrantIndex(qdrant, settings.qdrant_collection)

    def close() -> None:
        pool.close()
        qdrant.close()

    try:
        repository.create_schema()
        history.create_schema()
    except Exception:
        close()
        raise

    embedder = BgeEmbedder(
        model_name=settings.embedding_model,
        revision=settings.embedding_model_revision,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        max_length=settings.embedding_max_length,
    )
    search = SearchService(
        embedder,
        index,
        repository,
        threshold=settings.match_threshold,
        candidates=settings.search_candidates,
        top_k=settings.search_top_k,
        ambiguity_margin=settings.ambiguity_margin,
        ambiguity_max_words=settings.ambiguity_max_words,
    )

    def check() -> None:
        repository.ping()
        index.ping()

    def warm_up() -> None:
        embedder.embed([WARM_UP_TEXT])

    return Container(
        search=search,
        conversation=ConversationService(search, history),
        ingestion=IngestionService(repository, index, embedder, batch_size=settings.embedding_batch_size),
        check=check,
        warm_up=warm_up,
        close=close,
    )
