from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tenderlens.api.dependencies import get_qa_service
from tenderlens.api.routes.questions import router
from tenderlens.qa.models import GroundedAnswer, VerifiedCitation


class FakeQuestionAnsweringService:
    async def answer(self, _document_id: UUID, _question: str) -> GroundedAnswer:
        return GroundedAnswer(
            answer="The budget is 1 000 000 RUB. [1]",
            citations=[
                VerifiedCitation(
                    number=1,
                    chunk_id=uuid4(),
                    page_number=2,
                    quote="Maximum budget: 1 000 000 RUB",
                    start_char=15,
                    end_char=46,
                )
            ],
            answer_mode="extractive",
            retrieval_mode="hybrid",
            grounded=True,
            disclaimer="Not legal advice.",
        )


def test_question_endpoint_returns_verified_citations() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_qa_service] = lambda: FakeQuestionAnsweringService()

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/documents/{uuid4()}/questions",
            json={"question": "What is the maximum budget?"},
        )

    assert response.status_code == 200
    assert response.json()["grounded"] is True
    assert response.json()["citations"][0]["page_number"] == 2
    assert response.json()["citations"][0]["start_char"] == 15
