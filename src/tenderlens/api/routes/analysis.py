from uuid import UUID

from fastapi import APIRouter

from tenderlens.api.dependencies import DocumentAnalysisServiceDependency
from tenderlens.api.schemas.analysis import DocumentAnalysisResponse

router = APIRouter(prefix="/documents")


@router.post("/{document_id}/analysis", response_model=DocumentAnalysisResponse)
async def analyze_document(
    document_id: UUID,
    analysis_service: DocumentAnalysisServiceDependency,
) -> DocumentAnalysisResponse:
    result = await analysis_service.analyze(document_id)
    return DocumentAnalysisResponse.model_validate(result, from_attributes=True)
