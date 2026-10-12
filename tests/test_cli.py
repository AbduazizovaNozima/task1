from unittest.mock import Mock

import pytest

from app import cli
from app.domain.errors import StorageUnavailableError


def test_ingestion_waits_for_storage_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    check = Mock(side_effect=[StorageUnavailableError("not ready"), None])
    monkeypatch.setattr("time.sleep", lambda _: None)
    cli.wait_for_storage(check)
    assert check.call_count == 2


def test_storage_readiness_wait_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    check = Mock(side_effect=StorageUnavailableError("not ready"))
    clock = iter([0.0, 61.0])
    monkeypatch.setattr("time.monotonic", lambda: next(clock))
    with pytest.raises(StorageUnavailableError):
        cli.wait_for_storage(check)
    assert check.call_count == 1
