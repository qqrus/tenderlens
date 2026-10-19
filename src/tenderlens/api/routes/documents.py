from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Query, UploadFile, status
from fastapi.responses import FileResponse

from tenderlens.api.dependencies import IngestionServiceDependency
from tenderlens.api.schemas.documents import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from tenderlens.api.schemas.table_answers import TableAnswerRequest, TableAnswerResponse
from tenderlens.core.errors import AppError
from tenderlens.domain.documents import DocumentStatus
from tenderlens.ingestion.geometry_snapshot import GeometrySnapshot
from tenderlens.ingestion.table_geometry import select_cell

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


@router.get("/{document_id}/tables", response_model=GeometrySnapshot)
async def get_document_tables(
    document_id: UUID,
    ingestion_service: IngestionServiceDependency,
) -> GeometrySnapshot:
    document = await ingestion_service.get_document(document_id)
    if document is None:
        raise AppError(
            code="document_not_found", message="Document was not found.", status_code=404
        )
    if document.table_geometry is None:
        return GeometrySnapshot(source_sha256=document.sha256, status="not_processed")
    snapshot = GeometrySnapshot.model_validate(document.table_geometry)
    if snapshot.source_sha256 != document.sha256:
        raise AppError(
            code="geometry_source_mismatch", message="Geometry source mismatch.", status_code=409
        )
    return snapshot


@router.post("/{document_id}/table-answer", response_model=TableAnswerResponse)
async def answer_table_cell(
    document_id: UUID,
    request: TableAnswerRequest,
    ingestion_service: IngestionServiceDependency,
) -> TableAnswerResponse:
    document = await ingestion_service.get_document(document_id)
    if document is None:
        raise AppError(
            code="document_not_found", message="Document was not found.", status_code=404
        )
    snapshot = await get_document_tables(document_id, ingestion_service)
    if request.source_sha256 != snapshot.source_sha256:
        raise AppError(
            code="geometry_source_mismatch", message="Reload the source.", status_code=409
        )
    if document.status != DocumentStatus.READY.value or snapshot.status != "ready":
        raise AppError(
            code="table_not_ready", message="Table geometry is not ready.", status_code=409
        )
    if request.table_index >= len(snapshot.tables):
        raise AppError(code="table_not_found", message="Table was not found.", status_code=404)
    table = snapshot.tables[request.table_index]
    evidence = select_cell([table], request.row_label, request.column_header)
    if evidence is None:
        raise AppError(
            code="table_cell_ambiguous",
            message="No unique non-empty cell matches the row and column.",
            status_code=422,
        )
    return TableAnswerResponse(
        document_id=document_id,
        source_sha256=snapshot.source_sha256,
        page_width=table.page_width,
        page_height=table.page_height,
        evidence=evidence,
    )
