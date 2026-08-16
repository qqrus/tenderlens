from uuid import UUID

from fastapi import APIRouter

from tenderlens.api.dependencies import RetrievalServiceDependency
from tenderlens.api.schemas.search import SearchHitResponse, SearchRequest, SearchResponse

router = APIRouter(prefix="/documents")


@router.post("/{document_id}/search", response_model=SearchResponse)
async def search_document(
    document_id: UUID,
    request: SearchRequest,
    retrieval_service: RetrievalServiceDependency,
) -> SearchResponse:
    result = await retrieval_service.search(document_id, request.query, request.limit)
    return SearchResponse(
        mode=result.mode,
        hits=[SearchHitResponse.model_validate(hit, from_attributes=True) for hit in result.hits],
    )
