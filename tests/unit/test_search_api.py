from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tenderlens.api.dependencies import get_retrieval_service
from tenderlens.api.routes.search import router
from tenderlens.retrieval.service import RetrievalHit, RetrievalResult


class FakeRetrievalService:
    async def search(self, _document_id: UUID, _query: str, _limit: int | None) -> RetrievalResult:
        return RetrievalResult(
            mode="hybrid",
            hits=[
                RetrievalHit(
                    chunk_id=uuid4(),
                    page_number=2,
                    text="Maximum budget: 1000000 RUB",
                    start_char=0,
                    end_char=27,
                    rrf_score=0.03,
                    semantic_score=0.82,
                    lexical_score=0.7,
                )
            ],
        )


def test_search_endpoint_returns_page_scoped_hits() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_retrieval_service] = lambda: FakeRetrievalService()

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/documents/{uuid4()}/search",
            json={"query": "maximum budget", "limit": 3},
        )

    assert response.status_code == 200
    assert response.json()["mode"] == "hybrid"
    assert response.json()["hits"][0]["page_number"] == 2
