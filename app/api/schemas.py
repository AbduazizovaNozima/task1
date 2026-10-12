import unicodedata

from pydantic import BaseModel, Field, field_validator

QUESTION_MAX_LENGTH = 1000
CONTROL_CATEGORIES = frozenset({"Cc", "Cf"})


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=QUESTION_MAX_LENGTH, examples=["ID karta olish uchun nima kerak?"])

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Savol matni bo'sh.")
        if any(unicodedata.category(char) in CONTROL_CATEGORIES for char in value):
            raise ValueError("Savolda boshqaruv belgilariga ruxsat berilmaydi.")
        return value


class AskResponse(BaseModel):
    found: bool
    answer: str | None
    matched_question: str | None
    score: float | None
    suggestions: list[str]


class IngestResponse(BaseModel):
    rows_read: int
    rows_skipped: int
    answers: int
    questions: int
    newly_indexed: int


class HealthResponse(BaseModel):
    status: str
