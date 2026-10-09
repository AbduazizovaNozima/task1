from collections.abc import Sequence
from itertools import batched
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, PointStruct, Record, ScoredPoint, VectorParams

from app.domain.errors import IndexNotReadyError
from app.domain.models import Question, VectorHit

ANSWER_ID = "answer_id"
RETRIEVE_BATCH = 1000
NOT_FOUND = 404


class QdrantIndex:
    def __init__(self, client: QdrantClient, collection: str) -> None:
        self._client = client
        self._collection = collection

    def upsert(self, questions: Sequence[Question], vectors: Sequence[Sequence[float]]) -> None:
        self._ensure_collection(dimension=len(vectors[0]))
        points = [
            PointStruct(id=str(question.id), vector=list(vector), payload={ANSWER_ID: str(question.answer_id)})
            for question, vector in zip(questions, vectors, strict=True)
        ]
        self._client.upsert(collection_name=self._collection, points=points, wait=True)

    def indexed_answer_ids(self, question_ids: Sequence[UUID]) -> dict[UUID, UUID]:
        if not self._client.collection_exists(self._collection):
            return {}
        found: dict[UUID, UUID] = {}
        for batch in batched(question_ids, RETRIEVE_BATCH):
            records = self._client.retrieve(
                collection_name=self._collection,
                ids=[str(question_id) for question_id in batch],
                with_payload=True,
                with_vectors=False,
            )
            found.update((UUID(str(record.id)), _answer_id(record)) for record in records)
        return found

    def search(self, vector: Sequence[float], limit: int) -> list[VectorHit]:
        try:
            response = self._client.query_points(
                collection_name=self._collection,
                query=list(vector),
                limit=limit,
                with_payload=True,
            )
        except UnexpectedResponse as exc:
            if exc.status_code == NOT_FOUND:
                raise IndexNotReadyError("Qidiruv indeksi bo'sh: avval ma'lumotlarni yuklang.") from exc
            raise
        return [
            VectorHit(question_id=UUID(str(point.id)), answer_id=_answer_id(point), score=point.score)
            for point in response.points
        ]

    def _ensure_collection(self, dimension: int) -> None:
        if self._client.collection_exists(self._collection):
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
        )


def _answer_id(point: Record | ScoredPoint) -> UUID:
    return UUID(str((point.payload or {})[ANSWER_ID]))
