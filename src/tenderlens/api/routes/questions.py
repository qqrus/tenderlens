from uuid import UUID

from fastapi import APIRouter

from tenderlens.api.dependencies import QuestionAnsweringServiceDependency
from tenderlens.api.schemas.questions import AnswerResponse, CitationResponse, QuestionRequest

router = APIRouter(prefix="/documents")


@router.post("/{document_id}/questions", response_model=AnswerResponse)
async def answer_document_question(
    document_id: UUID,
    request: QuestionRequest,
    qa_service: QuestionAnsweringServiceDependency,
) -> AnswerResponse:
    result = await qa_service.answer(document_id, request.question)
    return AnswerResponse(
        answer=result.answer,
        citations=[
            CitationResponse.model_validate(citation, from_attributes=True)
            for citation in result.citations
        ],
        answer_mode=result.answer_mode,
        retrieval_mode=result.retrieval_mode,
        grounded=result.grounded,
        disclaimer=result.disclaimer,
    )
