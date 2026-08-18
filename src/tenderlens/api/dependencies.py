from typing import Annotated

from fastapi import Depends, Request

from tenderlens.analysis.service import DocumentAnalysisService
from tenderlens.ingestion.service import DocumentIngestionService
from tenderlens.qa.service import GroundedQuestionAnsweringService
from tenderlens.retrieval.service import HybridRetrievalService


def get_ingestion_service(request: Request) -> DocumentIngestionService:
    service = request.app.state.ingestion_service
    if not isinstance(service, DocumentIngestionService):
        raise RuntimeError("Document ingestion service is not configured.")
    return service


IngestionServiceDependency = Annotated[DocumentIngestionService, Depends(get_ingestion_service)]


def get_retrieval_service(request: Request) -> HybridRetrievalService:
    service = request.app.state.retrieval_service
    if not isinstance(service, HybridRetrievalService):
        raise RuntimeError("Hybrid retrieval service is not configured.")
    return service


RetrievalServiceDependency = Annotated[HybridRetrievalService, Depends(get_retrieval_service)]


def get_qa_service(request: Request) -> GroundedQuestionAnsweringService:
    service = request.app.state.qa_service
    if not isinstance(service, GroundedQuestionAnsweringService):
        raise RuntimeError("Question answering service is not configured.")
    return service


QuestionAnsweringServiceDependency = Annotated[
    GroundedQuestionAnsweringService,
    Depends(get_qa_service),
]


def get_analysis_service(request: Request) -> DocumentAnalysisService:
    service = request.app.state.analysis_service
    if not isinstance(service, DocumentAnalysisService):
        raise RuntimeError("Document analysis service is not configured.")
    return service


DocumentAnalysisServiceDependency = Annotated[
    DocumentAnalysisService,
    Depends(get_analysis_service),
]
