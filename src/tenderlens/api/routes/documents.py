from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Query, UploadFile, status
from fastapi.responses import FileResponse

from tenderlens.api.dependencies import IngestionServiceDependency
from tenderlens.api.schemas.documents import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from tenderlens.core.errors import AppError

router = APIRouter(prefix="/documents")


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    ingestion_service: IngestionServiceDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DocumentListResponse:
    documents, total = await ingestion_service.list_documents(limit=limit, offset=offset)
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(document) for document in documents],
        total=total,
        limit=limit,
        offset=offset,
    )


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


@router.get("/{document_id}/file", response_class=FileResponse)
async def get_document_file(
    document_id: UUID,
    ingestion_service: IngestionServiceDependency,
) -> FileResponse:
    source = await ingestion_service.get_document_source(document_id)
    if source is None:
        raise AppError(
            code="document_not_found",
            message="Document was not found.",
            status_code=404,
        )
    document, path = source
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=document.original_filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},
    )
