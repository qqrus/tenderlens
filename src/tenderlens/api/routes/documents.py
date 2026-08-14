from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, UploadFile, status

from tenderlens.api.dependencies import IngestionServiceDependency
from tenderlens.api.schemas.documents import DocumentResponse, DocumentUploadResponse
from tenderlens.core.errors import AppError

router = APIRouter(prefix="/documents")


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    ingestion_service: IngestionServiceDependency,
    file: UploadFile = File(description="Tender document in PDF format."),
) -> DocumentUploadResponse:
    document, deduplicated = await ingestion_service.register_upload(file)
    if not deduplicated:
        background_tasks.add_task(ingestion_service.process, document.id)
    return DocumentUploadResponse(
        document=DocumentResponse.model_validate(document),
        deduplicated=deduplicated,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    ingestion_service: IngestionServiceDependency,
) -> DocumentResponse:
    document = await ingestion_service.get_document(document_id)
    if document is None:
        raise AppError(
            code="document_not_found",
            message="Document was not found.",
            status_code=404,
        )
    return DocumentResponse.model_validate(document)
