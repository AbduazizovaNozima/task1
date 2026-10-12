import json
import logging
from collections.abc import Sequence
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.adapters.excel_reader import read_qa_sheet
from app.api.deps import get_container, get_ingestion, get_search, get_settings
from app.api.schemas import AskRequest, AskResponse, HealthResponse, IngestResponse
from app.config import Settings
from app.container import Container
from app.domain.errors import InvalidSpreadsheetError
from app.domain.models import Candidate, SearchResult
from app.services.ingestion import IngestionService
from app.services.search import SearchService

BYTES_IN_MB = 1024 * 1024
XLSX_SUFFIX = ".xlsx"

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
def health(container: Annotated[Container, Depends(get_container)]) -> HealthResponse:
    container.check()
    return HealthResponse(status="ok")


@router.post("/ask")
def ask(
    payload: AskRequest,
    response: Response,
    search: Annotated[SearchService, Depends(get_search)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AskResponse:
    request_id = uuid4().hex[:8]
    response.headers["X-Request-ID"] = request_id

    def log_decision(candidates: Sequence[Candidate], result: SearchResult, reason: str, threshold: float) -> None:
        for rank, candidate in enumerate(candidates[: settings.log_top_k], 1):
            logger.info(
                "candidate request_id=%s rank=%d score=%.3f answer_id=%s matched_question=%s",
                request_id,
                rank,
                candidate.score,
                candidate.answer_id,
                json.dumps(" ".join(candidate.question.splitlines())[:120], ensure_ascii=False),
            )
        logger.info(
            "decision request_id=%s found=%s chosen_rank=%s score=%s threshold=%.3f "
            "margin_to_threshold=%s reason=%s answer=%s",
            request_id,
            str(result.found).lower(),
            1 if result.found else "null",
            f"{result.score:.3f}" if result.score is not None else "null",
            threshold,
            f"{result.score - threshold:+.3f}" if result.score is not None else "null",
            reason,
            json.dumps(" ".join((result.answer or "").splitlines())[:80], ensure_ascii=False),
        )

    if settings.log_questions:
        logger.info(
            "ask request_id=%s question=%s",
            request_id,
            json.dumps(" ".join(payload.question.splitlines())[:200], ensure_ascii=False),
        )
    result = search.ask(payload.question, observe=log_decision if settings.log_questions else None)
    return AskResponse.model_validate(result.model_dump())


@router.post("/ingest")
def ingest(
    file: Annotated[UploadFile, File(description="Q&A Excel file with 'question' and 'answer' columns")],
    ingestion: Annotated[IngestionService, Depends(get_ingestion)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> IngestResponse:
    _validate_upload(file, settings.max_upload_mb)
    report = ingestion.ingest(read_qa_sheet(file.file))
    return IngestResponse.model_validate(report.model_dump())


def _validate_upload(file: UploadFile, max_upload_mb: int) -> None:
    if not (file.filename or "").lower().endswith(XLSX_SUFFIX):
        raise InvalidSpreadsheetError("Faqat .xlsx fayl qabul qilinadi.")
    if (file.size or 0) > max_upload_mb * BYTES_IN_MB:
        raise InvalidSpreadsheetError(f"Fayl hajmi {max_upload_mb} MB dan oshmasligi kerak.")
