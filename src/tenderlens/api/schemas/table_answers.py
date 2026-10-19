from uuid import UUID

from pydantic import BaseModel, Field

from tenderlens.ingestion.table_geometry import CellEvidence


class TableAnswerRequest(BaseModel):
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    table_index: int = Field(ge=0)
    row_label: str = Field(min_length=1, max_length=4000)
    column_header: str = Field(min_length=1, max_length=4000)


class TableAnswerResponse(BaseModel):
    document_id: UUID
    source_sha256: str
    page_width: float
    page_height: float
    evidence: CellEvidence
