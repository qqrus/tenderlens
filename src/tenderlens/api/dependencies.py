from typing import Annotated

from fastapi import Depends, Request

from tenderlens.ingestion.service import DocumentIngestionService
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
