from collections.abc import Callable
from dataclasses import dataclass

from psycopg_pool import ConnectionPool
from qdrant_client import QdrantClient

from app.adapters.bge_embedder import BgeEmbedder
from app.adapters.pg_repository import PostgresRepository
from app.adapters.qdrant_index import QdrantIndex
from app.config import Settings
from app.services.ingestion import IngestionService
from app.services.search import SearchService


@dataclass(frozen=True)
class Container:
    search: SearchService
    ingestion: IngestionService
    close: Callable[[], None]


def build_container(settings: Settings) -> Container:
    pool = ConnectionPool(settings.database_url, max_size=settings.database_pool_size, open=True)
    repository = PostgresRepository(pool)
    repository.create_schema()

    qdrant = QdrantClient(url=settings.qdrant_url, timeout=settings.qdrant_timeout_seconds)
    index = QdrantIndex(qdrant, settings.qdrant_collection)

    embedder = BgeEmbedder(
        model_name=settings.embedding_model,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        max_length=settings.embedding_max_length,
    )

    def close() -> None:
        pool.close()
        qdrant.close()

    return Container(
        search=SearchService(
            embedder,
            index,
            repository,
            threshold=settings.match_threshold,
            candidates=settings.search_candidates,
        ),
        ingestion=IngestionService(repository, index, embedder, batch_size=settings.embedding_batch_size),
        close=close,
    )
