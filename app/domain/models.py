from uuid import UUID

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class QAPair(_Frozen):
    question: str
    answer: str


class SkippedRow(_Frozen):
    row: int
    reason: str


class QASheet(_Frozen):
    pairs: list[QAPair]
    skipped: list[SkippedRow]


class Answer(_Frozen):
    id: UUID
    text: str


class Question(_Frozen):
    id: UUID
    answer_id: UUID
    text: str


class QARecord(_Frozen):
    question: str
    answer: str


class VectorHit(_Frozen):
    question_id: UUID
    answer_id: UUID
    score: float


class Candidate(_Frozen):
    answer_id: UUID
    question: str
    answer: str
    score: float


class SearchResult(_Frozen):
    found: bool
    score: float | None
    answer_id: UUID | None = None
    answer: str | None = None
    matched_question: str | None = None
    suggestions: list[str] = []
    context_used: bool = False
    candidates: list[Candidate] = []


class ChatTurn(_Frozen):
    topic: str
    answer_id: UUID | None


class IngestReport(_Frozen):
    rows_read: int
    rows_skipped: int
    answers: int
    questions: int
    newly_indexed: int
