import httpx
from pydantic import BaseModel


class AskReply(BaseModel):
    found: bool
    answer: str | None
    matched_question: str | None
    score: float | None


class QAApiError(Exception):
    pass


class QAApiClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._http = httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)

    async def ask(self, question: str) -> AskReply:
        try:
            response = await self._http.post("/ask", json={"question": question})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise QAApiError(str(exc)) from exc
        return AskReply.model_validate(response.json())

    async def close(self) -> None:
        await self._http.aclose()
