from unittest.mock import Mock

import pytest

from app import container
from app.config import Settings


@pytest.mark.parametrize("failure", ["client", "schema"])
def test_partial_initialization_closes_opened_resources(monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    pool, client, repository = Mock(), Mock(), Mock()
    monkeypatch.setattr(container, "ConnectionPool", Mock(return_value=pool))
    monkeypatch.setattr(container, "PostgresRepository", Mock(return_value=repository))
    constructor = Mock(side_effect=ValueError("invalid URL")) if failure == "client" else Mock(return_value=client)
    monkeypatch.setattr(container, "QdrantClient", constructor)
    repository.create_schema.side_effect = RuntimeError("schema failed")
    with pytest.raises((ValueError, RuntimeError)):
        container.build_container(Settings(_env_file=None))
    pool.close.assert_called_once_with()
    if failure == "schema":
        client.close.assert_called_once_with()
