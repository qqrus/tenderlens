from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from tenderlens.domain.documents import DocumentStatus


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    page_count: int | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    deduplicated: bool


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    limit: int
    offset: int
