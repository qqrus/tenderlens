from typing import Annotated

from fastapi import Depends, Request

from tenderlens.ingestion.service import DocumentIngestionService


def get_ingestion_service(request: Request) -> DocumentIngestionService:
    service = request.app.state.ingestion_service
    if not isinstance(service, DocumentIngestionService):
        raise RuntimeError("Document ingestion service is not configured.")
    return service


IngestionServiceDependency = Annotated[DocumentIngestionService, Depends(get_ingestion_service)]
