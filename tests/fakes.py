import math
import zlib
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.domain.models import Answer, ChatTurn, QAPair, QARecord, QASheet, Question, VectorHit
from app.services.conversation import ConversationService
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

    def get_many(self, question_ids: Sequence[UUID]) -> dict[UUID, QARecord]:
        return {
            qid: QARecord(question=self.questions[qid].text, answer=self.answers[self.questions[qid].answer_id].text)
            for qid in question_ids
            if qid in self.questions
        }


class InMemoryChatHistory:
    def __init__(self) -> None:
        self.sessions: dict[str, ChatTurn] = {}

    def last(self, session_id: str) -> ChatTurn | None:
        return self.sessions.get(session_id)

    def save(self, session_id: str, turn: ChatTurn) -> None:
        self.sessions[session_id] = turn

    def clear(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)


@dataclass(frozen=True)
class Services:
    repository: InMemoryRepository
    index: InMemoryIndex
    embedder: FakeEmbedder
    history: InMemoryChatHistory
    search: SearchService
    conversation: ConversationService
    ingestion: IngestionService


def build_services(
    pairs: Sequence[QAPair] = (),
    threshold: float = 0.6,
    ambiguity_margin: float = 0.0,
) -> Services:
    repository, index, embedder, history = InMemoryRepository(), InMemoryIndex(), FakeEmbedder(), InMemoryChatHistory()
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
    conversation = ConversationService(search, history)
    return Services(repository, index, embedder, history, search, conversation, ingestion)
