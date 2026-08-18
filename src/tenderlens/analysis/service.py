from uuid import UUID

from tenderlens.analysis.extractor import CATEGORY_SPECS, RuleBasedConditionExtractor
from tenderlens.analysis.models import (
    AnalysisCoverage,
    ConditionCategory,
    DocumentAnalysis,
    ExtractedCondition,
    RiskCheck,
    RiskSeverity,
)
from tenderlens.qa.service import DISCLAIMER
from tenderlens.retrieval.service import HybridRetrievalService, RetrievalHit


class DocumentAnalysisService:
    def __init__(
        self,
        retrieval_service: HybridRetrievalService,
        extractor: RuleBasedConditionExtractor,
        *,
        retrieval_limit: int,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.extractor = extractor
        self.retrieval_limit = retrieval_limit

    async def analyze(self, document_id: UUID) -> DocumentAnalysis:
        conditions: list[ExtractedCondition] = []
        retrieval_modes: set[str] = set()
        for spec in CATEGORY_SPECS:
            hits: list[RetrievalHit] = []
            seen_chunks: set[UUID] = set()
            for query in spec.queries:
                result = await self.retrieval_service.search(
                    document_id,
                    query,
                    self.retrieval_limit,
                )
                retrieval_modes.add(result.mode)
                for hit in result.hits:
                    if hit.chunk_id not in seen_chunks:
                        seen_chunks.add(hit.chunk_id)
                        hits.append(hit)
            extracted = self.extractor.extract(
                spec,
                hits,
                citation_start=len(conditions) + 1,
            )
            conditions.extend(extracted)

        found = [
            category
            for category in ConditionCategory
            if any(condition.category == category for condition in conditions)
        ]
        missing = [category for category in ConditionCategory if category not in found]
        risks = build_risk_checklist(conditions, missing)
        return DocumentAnalysis(
            document_id=document_id,
            conditions=conditions,
            risks=risks,
            coverage=AnalysisCoverage(found_categories=found, missing_categories=missing),
            retrieval_modes=sorted(retrieval_modes),
            disclaimer=DISCLAIMER,
        )


def build_risk_checklist(
    conditions: list[ExtractedCondition],
    missing_categories: list[ConditionCategory],
) -> list[RiskCheck]:
    first_by_category = {
        category: next(
            (condition for condition in conditions if condition.category == category),
            None,
        )
        for category in ConditionCategory
    }
    present_rules = {
        ConditionCategory.DEADLINE: (
            "deadline_compliance",
            RiskSeverity.HIGH,
            "Deadline compliance",
            "The document contains a submission or delivery deadline.",
            "Confirm the timezone, submission channel, and an earlier internal cutoff.",
        ),
        ConditionCategory.BUDGET: (
            "budget_fit",
            RiskSeverity.MEDIUM,
            "Budget fit",
            "The document contains a budget or contract value condition.",
            "Validate taxes, currency, included costs, and commercial feasibility.",
        ),
        ConditionCategory.PENALTY: (
            "penalty_exposure",
            RiskSeverity.HIGH,
            "Penalty exposure",
            "The document contains a penalty, fine, or liquidated damages condition.",
            "Quantify the maximum exposure and review triggering events manually.",
        ),
        ConditionCategory.REQUIREMENT: (
            "eligibility_evidence",
            RiskSeverity.HIGH,
            "Eligibility evidence",
            "The document contains bidder or supplier requirements.",
            "Map every requirement to an owner and supporting document before submission.",
        ),
    }
    risks: list[RiskCheck] = []
    for category, rule in present_rules.items():
        condition = first_by_category[category]
        if condition is None:
            continue
        rule_id, severity, title, description, recommendation = rule
        risks.append(
            RiskCheck(
                rule_id=rule_id,
                severity=severity,
                title=title,
                description=description,
                recommendation=recommendation,
                grounded=True,
                citation=condition.citation,
            )
        )

    for category in missing_categories:
        risks.append(
            RiskCheck(
                rule_id=f"missing_{category.value}",
                severity=RiskSeverity.HIGH,
                title=f"{category.value.title()} not found",
                description=(
                    f"Automatic analysis did not find an explicit {category.value} condition."
                ),
                recommendation="Review the original PDF manually before making a decision.",
                grounded=False,
                citation=None,
            )
        )
    return risks
