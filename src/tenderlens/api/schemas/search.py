from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1_000)
    limit: int | None = Field(default=None, ge=1, le=20)


class SearchHitResponse(BaseModel):
    chunk_id: UUID
    page_number: int
    text: str
    start_char: int
    end_char: int
    rrf_score: float
    semantic_score: float | None
    lexical_score: float | None


class SearchResponse(BaseModel):
    mode: str
    hits: list[SearchHitResponse]
