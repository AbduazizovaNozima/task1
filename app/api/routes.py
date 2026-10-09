from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.adapters.excel_reader import read_qa_sheet
from app.api.deps import get_container, get_conversation, get_ingestion, get_settings
from app.api.schemas import AskRequest, AskResponse, HealthResponse, IngestResponse
from app.config import Settings
from app.container import Container
from app.domain.errors import InvalidSpreadsheetError
from app.services.conversation import ConversationService
from app.services.ingestion import IngestionService

BYTES_IN_MB = 1024 * 1024
XLSX_SUFFIX = ".xlsx"

router = APIRouter()


@router.get("/health")
def health(container: Annotated[Container, Depends(get_container)]) -> HealthResponse:
    container.check()
    return HealthResponse(status="ok")


@router.post("/ask")
def ask(payload: AskRequest, conversation: Annotated[ConversationService, Depends(get_conversation)]) -> AskResponse:
    result = conversation.ask(payload.question, payload.session_id)
    return AskResponse.model_validate(result.model_dump())


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def reset_session(session_id: str, conversation: Annotated[ConversationService, Depends(get_conversation)]) -> None:
    conversation.reset(session_id)


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
