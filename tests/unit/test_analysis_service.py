from uuid import UUID, uuid4

import pytest

from tenderlens.analysis.extractor import RuleBasedConditionExtractor
from tenderlens.analysis.models import ConditionCategory, RiskSeverity
from tenderlens.analysis.service import DocumentAnalysisService
from tenderlens.retrieval.service import RetrievalHit, RetrievalResult


def make_hit(text: str, page: int) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=uuid4(),
        page_number=page,
        text=text,
        start_char=0,
        end_char=len(text),
        rrf_score=0.03,
        semantic_score=0.8,
        lexical_score=0.7,
    )


class FakeAnalysisRetrieval:
    async def search(self, _document_id: UUID, query: str, _limit: int) -> RetrievalResult:
        lowered = query.casefold()
        if "deadline" in lowered or "срок" in lowered:
            hit = make_hit("Submission deadline: 20 August 2026.", 1)
        elif "budget" in lowered or "бюджет" in lowered:
            hit = make_hit("Maximum budget: 1 000 000 RUB.", 2)
        elif "penalty" in lowered or "штраф" in lowered:
            hit = make_hit("Penalty: 0.1% of contract value per day.", 3)
        else:
            hit = make_hit("Supplier must provide an ISO 9001 certificate.", 4)
        return RetrievalResult(mode="hybrid", hits=[hit])


class DeadlineOnlyRetrieval:
    async def search(self, _document_id: UUID, _query: str, _limit: int) -> RetrievalResult:
        return RetrievalResult(
            mode="lexical",
            hits=[make_hit("Submission deadline: 20 August 2026.", 1)],
        )


@pytest.mark.asyncio
async def test_analysis_builds_conditions_coverage_and_grounded_risks() -> None:
    service = DocumentAnalysisService(
        FakeAnalysisRetrieval(),  # type: ignore[arg-type]
        RuleBasedConditionExtractor(3),
        retrieval_limit=8,
    )

    result = await service.analyze(uuid4())

    assert set(result.coverage.found_categories) == set(ConditionCategory)
    assert result.coverage.missing_categories == []
    assert len(result.conditions) == 4
    assert all(risk.grounded for risk in result.risks)
    penalty_risk = next(risk for risk in result.risks if risk.rule_id == "penalty_exposure")
    assert penalty_risk.severity == RiskSeverity.HIGH
    assert penalty_risk.citation is not None
    assert penalty_risk.citation.page_number == 3


@pytest.mark.asyncio
async def test_analysis_flags_categories_not_found_for_manual_review() -> None:
    service = DocumentAnalysisService(
        DeadlineOnlyRetrieval(),  # type: ignore[arg-type]
        RuleBasedConditionExtractor(3),
        retrieval_limit=8,
    )

    result = await service.analyze(uuid4())

    assert result.coverage.found_categories == [ConditionCategory.DEADLINE]
    assert ConditionCategory.BUDGET in result.coverage.missing_categories
    missing_budget = next(risk for risk in result.risks if risk.rule_id == "missing_budget")
    assert missing_budget.grounded is False
    assert missing_budget.citation is None
    assert "manually" in missing_budget.recommendation
