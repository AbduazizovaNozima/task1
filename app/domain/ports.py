from collections.abc import Sequence
from contextlib import AbstractContextManager
from typing import Protocol
from uuid import UUID

from app.domain.models import Answer, QARecord, Question, VectorHit


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class VectorIndex(Protocol):
    def upsert(self, questions: Sequence[Question], vectors: Sequence[Sequence[float]]) -> None: ...

    def indexed_answer_ids(self, question_ids: Sequence[UUID]) -> dict[UUID, UUID]: ...

    def search(self, vector: Sequence[float], limit: int) -> list[VectorHit]: ...


class QARepository(Protocol):
    def upsert_transaction(
        self, answers: Sequence[Answer], questions: Sequence[Question]
    ) -> AbstractContextManager[None]: ...

    def get_many(self, question_ids: Sequence[UUID]) -> dict[UUID, QARecord]: ...
