import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from psycopg import OperationalError
from psycopg_pool import ConnectionPool
from qdrant_client import QdrantClient

from app.adapters.pg_repository import PostgresRepository
from app.adapters.qdrant_index import QdrantIndex
from app.domain.errors import IndexNotReadyError
from app.domain.models import Answer, Question
from tests.fakes import bag_of_words

pytestmark = pytest.mark.integration

DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://qa:qa@localhost:5440/semantic_qa")
QDRANT_URL = os.environ.get("TEST_QDRANT_URL", "http://localhost:6333")


@pytest.fixture
def repository() -> Iterator[PostgresRepository]:
    try:
        pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=1, open=True, timeout=3)
    except OperationalError:
        pytest.skip("PostgreSQL is not reachable")
    repository = PostgresRepository(pool)
    repository.create_schema()
    yield repository
    pool.close()


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

    record = repository.get(question.id)
    assert record is not None
    assert (record.question, record.answer) == ("Pasport qanday olinadi?", "DXM orqali.")
    assert repository.get(uuid4()) is None


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
