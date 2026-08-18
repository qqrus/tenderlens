from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from tenderlens.qa.models import VerifiedCitation


class ConditionCategory(StrEnum):
    DEADLINE = "deadline"
    BUDGET = "budget"
    PENALTY = "penalty"
    REQUIREMENT = "requirement"


class RiskSeverity(StrEnum):
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class ExtractedCondition:
    category: ConditionCategory
    summary: str
    match_score: float
    citation: VerifiedCitation


@dataclass(frozen=True, slots=True)
class RiskCheck:
    rule_id: str
    severity: RiskSeverity
    title: str
    description: str
    recommendation: str
    grounded: bool
    citation: VerifiedCitation | None


@dataclass(frozen=True, slots=True)
class AnalysisCoverage:
    found_categories: list[ConditionCategory]
    missing_categories: list[ConditionCategory]


@dataclass(frozen=True, slots=True)
class DocumentAnalysis:
    document_id: UUID
    conditions: list[ExtractedCondition]
    risks: list[RiskCheck]
    coverage: AnalysisCoverage
    retrieval_modes: list[str]
    disclaimer: str
