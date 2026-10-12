import math
import zlib
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from app.domain.models import Answer, QAPair, QARecord, QASheet, Question, VectorHit
from app.services.ingestion import IngestionService
from app.services.search import SearchService

DIMENSION = 64


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [bag_of_words(text) for text in texts]


def bag_of_words(text: str) -> list[float]:
    vector = [0.0] * DIMENSION
    for word in text.split():
        vector[zlib.crc32(word.encode()) % DIMENSION] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class InMemoryIndex:
    def __init__(self) -> None:
        self.points: dict[UUID, tuple[UUID, list[float]]] = {}

    def upsert(self, questions: Sequence[Question], vectors: Sequence[Sequence[float]]) -> None:
        for question, vector in zip(questions, vectors, strict=True):
            self.points[question.id] = (question.answer_id, list(vector))

    def indexed_answer_ids(self, question_ids: Sequence[UUID]) -> dict[UUID, UUID]:
        return {qid: self.points[qid][0] for qid in question_ids if qid in self.points}

    def search(self, vector: Sequence[float], limit: int) -> list[VectorHit]:
        hits = [
            VectorHit(
                question_id=qid, answer_id=answer_id, score=sum(a * b for a, b in zip(vector, stored, strict=True))
            )
            for qid, (answer_id, stored) in self.points.items()
        ]
        return sorted(hits, key=lambda h: h.score, reverse=True)[:limit]


class InMemoryRepository:
    def __init__(self) -> None:
        self.answers: dict[UUID, Answer] = {}
        self.questions: dict[UUID, Question] = {}

    def upsert(self, answers: Sequence[Answer], questions: Sequence[Question]) -> None:
        self.answers.update((a.id, a) for a in answers)
        self.questions.update((q.id, q) for q in questions)

    @contextmanager
    def upsert_transaction(self, answers: Sequence[Answer], questions: Sequence[Question]) -> Iterator[None]:
        old_answers, old_questions = self.answers.copy(), self.questions.copy()
        try:
            self.upsert(answers, questions)
            yield
        except Exception:
            self.answers, self.questions = old_answers, old_questions
            raise

    def get_many(self, question_ids: Sequence[UUID]) -> dict[UUID, QARecord]:
        return {
            qid: QARecord(question=self.questions[qid].text, answer=self.answers[self.questions[qid].answer_id].text)
            for qid in question_ids
            if qid in self.questions
        }


@dataclass(frozen=True)
class Services:
    repository: InMemoryRepository
    index: InMemoryIndex
    embedder: FakeEmbedder
    search: SearchService
    ingestion: IngestionService


def build_services(
    pairs: Sequence[QAPair] = (),
    threshold: float = 0.6,
    ambiguity_margin: float = 0.0,
) -> Services:
    repository, index, embedder = InMemoryRepository(), InMemoryIndex(), FakeEmbedder()
    ingestion = IngestionService(repository, index, embedder, batch_size=8)
    if pairs:
        ingestion.ingest(QASheet(pairs=list(pairs), skipped=[]))
    search = SearchService(
        embedder,
        index,
        repository,
        threshold=threshold,
        candidates=10,
        top_k=3,
        ambiguity_margin=ambiguity_margin,
        ambiguity_max_words=2,
    )
    return Services(repository, index, embedder, search, ingestion)
