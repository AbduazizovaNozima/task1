import httpx
from pydantic import BaseModel, Field


class AskReply(BaseModel):
    found: bool
    answer: str | None
    matched_question: str | None
    score: float | None
    suggestions: list[str] = []
    request_id: str | None = Field(default=None, exclude=True)


class QAApiError(Exception):
    pass


class QAApiValidationError(QAApiError):
    pass


class QAApiClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._http = httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)

    async def ask(self, question: str) -> AskReply:
        try:
            response = await self._http.post("/ask", json={"question": question})
            if response.status_code == httpx.codes.UNPROCESSABLE_ENTITY:
                raise QAApiValidationError("Question rejected by the API")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise QAApiError(str(exc)) from exc
        try:
            reply = AskReply.model_validate(response.json())
            return reply.model_copy(update={"request_id": response.headers.get("X-Request-ID")})
        except ValueError as exc:
            raise QAApiError("Q&A API returned an invalid response") from exc

    async def close(self) -> None:
        await self._http.aclose()
