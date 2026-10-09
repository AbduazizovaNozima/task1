from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.adapters.excel_reader import read_qa_sheet
from app.api.deps import get_ingestion, get_search, get_settings
from app.api.schemas import AskRequest, AskResponse, HealthResponse, IngestResponse
from app.config import Settings
from app.domain.errors import InvalidSpreadsheetError
from app.services.ingestion import IngestionService
from app.services.search import SearchService

BYTES_IN_MB = 1024 * 1024
XLSX_SUFFIX = ".xlsx"

router = APIRouter()


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/ask")
def ask(payload: AskRequest, search: Annotated[SearchService, Depends(get_search)]) -> AskResponse:
    result = search.ask(payload.question)
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
