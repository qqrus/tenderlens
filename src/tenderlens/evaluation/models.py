from pydantic import BaseModel, Field

from tenderlens.analysis.models import ConditionCategory


class EvaluationQuestion(BaseModel):
    id: str = Field(min_length=1)
    language: str = Field(pattern=r"^(en|ru)$")
    question: str = Field(min_length=2)
    expected_pages: list[int] = Field(min_length=1)
    expected_quote_fragments: list[str] = Field(min_length=1)


class AnalysisExpectation(BaseModel):
    category: ConditionCategory
    expected_pages: list[int] = Field(min_length=1)


class EvaluationDataset(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    pages: list[str] = Field(min_length=1)
    questions: list[EvaluationQuestion] = Field(min_length=1)
    analysis_expectations: list[AnalysisExpectation] = Field(min_length=1)
