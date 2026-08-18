from uuid import UUID

from pydantic import BaseModel

from tenderlens.analysis.models import ConditionCategory, RiskSeverity
from tenderlens.api.schemas.questions import CitationResponse


class ExtractedConditionResponse(BaseModel):
    category: ConditionCategory
    summary: str
    match_score: float
    citation: CitationResponse


class RiskCheckResponse(BaseModel):
    rule_id: str
    severity: RiskSeverity
    title: str
    description: str
    recommendation: str
    grounded: bool
    citation: CitationResponse | None


class AnalysisCoverageResponse(BaseModel):
    found_categories: list[ConditionCategory]
    missing_categories: list[ConditionCategory]


class DocumentAnalysisResponse(BaseModel):
    document_id: UUID
    conditions: list[ExtractedConditionResponse]
    risks: list[RiskCheckResponse]
    coverage: AnalysisCoverageResponse
    retrieval_modes: list[str]
    disclaimer: str
