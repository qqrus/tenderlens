from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tenderlens.analysis.models import (
    AnalysisCoverage,
    ConditionCategory,
    DocumentAnalysis,
    ExtractedCondition,
    RiskCheck,
    RiskSeverity,
)
from tenderlens.api.dependencies import get_analysis_service
from tenderlens.api.routes.analysis import router
from tenderlens.qa.models import VerifiedCitation


class FakeAnalysisService:
    async def analyze(self, document_id: UUID) -> DocumentAnalysis:
        citation = VerifiedCitation(
            number=1,
            chunk_id=uuid4(),
            page_number=2,
            quote="Maximum budget: 1 000 000 RUB.",
            start_char=10,
            end_char=43,
        )
        return DocumentAnalysis(
            document_id=document_id,
            conditions=[
                ExtractedCondition(
                    category=ConditionCategory.BUDGET,
                    summary=citation.quote,
                    match_score=0.91,
                    citation=citation,
                )
            ],
            risks=[
                RiskCheck(
                    rule_id="budget_fit",
                    severity=RiskSeverity.MEDIUM,
                    title="Budget fit",
                    description="Budget found.",
                    recommendation="Validate costs.",
                    grounded=True,
                    citation=citation,
                )
            ],
            coverage=AnalysisCoverage(
                found_categories=[ConditionCategory.BUDGET],
                missing_categories=[ConditionCategory.DEADLINE],
            ),
            retrieval_modes=["hybrid"],
            disclaimer="Not legal advice.",
        )


def test_analysis_endpoint_returns_conditions_and_risks() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_analysis_service] = lambda: FakeAnalysisService()
    document_id = uuid4()

    with TestClient(app) as client:
        response = client.post(f"/api/v1/documents/{document_id}/analysis")

    assert response.status_code == 200
    assert response.json()["document_id"] == str(document_id)
    assert response.json()["conditions"][0]["category"] == "budget"
    assert response.json()["risks"][0]["citation"]["page_number"] == 2
    assert response.json()["coverage"]["missing_categories"] == ["deadline"]
