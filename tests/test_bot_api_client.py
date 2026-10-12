import asyncio

import httpx
import pytest

from bot.api_client import QAApiClient, QAApiError


@pytest.mark.parametrize("body", [b"not JSON", b"{}"])
def test_invalid_upstream_body_is_a_service_error(body: bytes) -> None:
    async def scenario() -> None:
        api = QAApiClient("http://api.test", 1)
        await api._http.aclose()
        api._http = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body)), base_url="http://api.test"
        )
        try:
            with pytest.raises(QAApiError):
                await api.ask("question", "user")
        finally:
            await api.close()

    asyncio.run(scenario())


def test_validation_status_is_not_a_service_outage() -> None:
    from bot.api_client import QAApiValidationError

    async def scenario() -> None:
        api = QAApiClient("http://api.test", 1)
        await api._http.aclose()
        api._http = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(422, json={"detail": "too long"})),
            base_url="http://api.test",
        )
        try:
            with pytest.raises(QAApiValidationError):
                await api.ask("x" * 1001, "user")
        finally:
            await api.close()

    asyncio.run(scenario())
