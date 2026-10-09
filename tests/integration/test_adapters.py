import os
from collections.abc import Iterator
from datetime import timedelta
from uuid import uuid4

import psycopg
import pytest
from psycopg_pool import ConnectionPool
from qdrant_client import QdrantClient

from app.adapters.pg_chat_history import PostgresChatHistory
from app.adapters.pg_repository import PostgresRepository
from app.adapters.qdrant_index import QdrantIndex
from app.domain.errors import IndexNotReadyError, StorageUnavailableError
from app.domain.models import Answer, ChatTurn, Question
from tests.fakes import bag_of_words

pytestmark = pytest.mark.integration

DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://qa:qa@localhost:5440/qa")
QDRANT_URL = os.environ.get("TEST_QDRANT_URL", "http://localhost:6333")
UNREACHABLE_DATABASE_URL = "postgresql://qa:qa@127.0.0.1:1/qa"
UNREACHABLE_QDRANT_URL = "http://127.0.0.1:1"
CONNECT_TIMEOUT_SECONDS = 3


@pytest.fixture
def pool() -> Iterator[ConnectionPool]:
    schema = f"test_{uuid4().hex}"
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=CONNECT_TIMEOUT_SECONDS) as admin:
            admin.execute(f'CREATE SCHEMA "{schema}"')
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL is not reachable")
    pool = ConnectionPool(
        DATABASE_URL,
        min_size=1,
        max_size=1,
        timeout=CONNECT_TIMEOUT_SECONDS,
        kwargs={"options": f"-c search_path={schema}"},
        open=True,
    )
    yield pool
    pool.close()
    with psycopg.connect(DATABASE_URL) as admin:
        admin.execute(f'DROP SCHEMA "{schema}" CASCADE')


@pytest.fixture
def repository(pool: ConnectionPool) -> PostgresRepository:
    repository = PostgresRepository(pool)
    repository.create_schema()
    return repository


@pytest.fixture
def index() -> Iterator[QdrantIndex]:
    client = QdrantClient(url=QDRANT_URL, timeout=3)
    try:
        client.get_collections()
    except Exception:
        pytest.skip("Qdrant is not reachable")
    collection = f"test_{uuid4().hex}"
    yield QdrantIndex(client, collection)
    client.delete_collection(collection)
    client.close()


def test_postgres_upsert_is_idempotent_and_get_joins_answer(repository: PostgresRepository) -> None:
    answer = Answer(id=uuid4(), text="DXM orqali.")
    question = Question(id=uuid4(), answer_id=answer.id, text="Pasport qanday olinadi?")

    repository.upsert([answer], [question])
    repository.upsert([answer], [question])

    records = repository.get_many([question.id, uuid4()])
    assert list(records) == [question.id]
    assert (records[question.id].question, records[question.id].answer) == ("Pasport qanday olinadi?", "DXM orqali.")


def test_qdrant_search_before_ingestion_reports_index_not_ready(index: QdrantIndex) -> None:
    with pytest.raises(IndexNotReadyError):
        index.search(bag_of_words("pasport"), limit=3)


def test_qdrant_upsert_search_and_lookup(index: QdrantIndex) -> None:
    answer_id = uuid4()
    questions = [
        Question(id=uuid4(), answer_id=answer_id, text="pasport qanday olinadi"),
        Question(id=uuid4(), answer_id=uuid4(), text="nikoh qayerda qayd etiladi"),
    ]
    vectors = [bag_of_words(q.text) for q in questions]

    index.upsert(questions, vectors)
    index.upsert(questions, vectors)

    hits = index.search(bag_of_words("pasport qanday olinadi"), limit=5)
    assert len(hits) == 2
    assert hits[0].question_id == questions[0].id
    assert hits[0].answer_id == answer_id
    assert hits[0].score == pytest.approx(1.0, abs=1e-4)
    assert index.indexed_answer_ids([questions[0].id, uuid4()]) == {questions[0].id: answer_id}


def test_postgres_chat_history_keeps_one_turn_per_session(pool: ConnectionPool) -> None:
    history = PostgresChatHistory(pool, ttl=timedelta(minutes=5))
    history.create_schema()
    answer_id = uuid4()

    history.save("user-1", ChatTurn(topic="pasport", answer_id=None))
    history.save("user-1", ChatTurn(topic="id karta", answer_id=answer_id))
    history.save("user-2", ChatTurn(topic="nikoh", answer_id=None))

    assert history.last("user-1") == ChatTurn(topic="id karta", answer_id=answer_id)
    assert history.last("user-2") == ChatTurn(topic="nikoh", answer_id=None)
    history.clear("user-1")
    assert history.last("user-1") is None


def test_postgres_chat_history_expires_old_turns(pool: ConnectionPool) -> None:
    history = PostgresChatHistory(pool, ttl=timedelta(0))
    history.create_schema()

    history.save("user-1", ChatTurn(topic="pasport", answer_id=None))

    assert history.last("user-1") is None


def test_unreachable_postgres_raises_storage_error() -> None:
    pool = ConnectionPool(UNREACHABLE_DATABASE_URL, min_size=1, max_size=1, timeout=1, open=True)
    try:
        with pytest.raises(StorageUnavailableError):
            PostgresRepository(pool).ping()
    finally:
        pool.close()


def test_unreachable_qdrant_raises_storage_error() -> None:
    index = QdrantIndex(QdrantClient(url=UNREACHABLE_QDRANT_URL, timeout=1), "qa_questions")

    with pytest.raises(StorageUnavailableError):
        index.ping()
