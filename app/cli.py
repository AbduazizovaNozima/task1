import argparse
import logging
import time
from collections.abc import Callable
from pathlib import Path

from app.adapters.excel_reader import read_qa_sheet
from app.config import Settings
from app.container import build_container
from app.domain.errors import InvalidSpreadsheetError, StorageUnavailableError
from app.log import configure_logging

logger = logging.getLogger(__name__)

STORAGE_READY_TIMEOUT_SECONDS = 60
STORAGE_RETRY_INTERVAL_SECONDS = 2


def wait_for_storage(check: Callable[[], None]) -> None:
    deadline = time.monotonic() + STORAGE_READY_TIMEOUT_SECONDS
    while True:
        try:
            check()
            return
        except StorageUnavailableError:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            logger.warning("Storage not ready; retrying startup check")
            time.sleep(min(STORAGE_RETRY_INTERVAL_SECONDS, remaining))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="load Q&A pairs from an .xlsx file")
    ingest.add_argument("path", type=Path)
    args = parser.parse_args(argv)

    if not args.path.is_file():
        parser.error(f"file not found: {args.path}")

    settings = Settings()
    configure_logging(settings.log_level)
    try:
        sheet = read_qa_sheet(args.path)
    except InvalidSpreadsheetError as exc:
        logger.error("%s: %s", args.path, exc)
        raise SystemExit(1) from exc

    container = build_container(settings)
    try:
        wait_for_storage(container.check)
        container.ingestion.ingest(sheet)
    finally:
        container.close()


if __name__ == "__main__":
    main()
