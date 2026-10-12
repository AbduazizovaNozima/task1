import httpx
from pydantic import BaseModel


class AskReply(BaseModel):
    found: bool
    answer: str | None
    matched_question: str | None
    score: float | None
    suggestions: list[str] = []


class QAApiError(Exception):
    pass


class QAApiValidationError(QAApiError):
    pass


class QAApiClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._http = httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)

    async def ask(self, question: str) -> AskReply:
        response = await self._send("POST", "/ask", json={"question": question})
        try:
            return AskReply.model_validate(response.json())
        except ValueError as exc:
            raise QAApiError("Q&A API returned an invalid response") from exc

    async def _send(self, method: str, path: str, json: dict[str, str] | None = None) -> httpx.Response:
        try:
            response = await self._http.request(method, path, json=json)
            if response.status_code == 422:
                raise QAApiValidationError("Question rejected by the API")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise QAApiError(str(exc)) from exc
        return response

    async def close(self) -> None:
        await self._http.aclose()
