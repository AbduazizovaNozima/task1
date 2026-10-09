from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000, examples=["ID karta olish uchun nima kerak?"])
    session_id: str | None = Field(default=None, min_length=1, max_length=100, examples=["telegram-123456"])


class AskResponse(BaseModel):
    found: bool
    answer: str | None
    matched_question: str | None
    score: float | None
    suggestions: list[str]
    context_used: bool


class IngestResponse(BaseModel):
    rows_read: int
    rows_skipped: int
    answers: int
    questions: int
    newly_indexed: int


class HealthResponse(BaseModel):
    status: str
