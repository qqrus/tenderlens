from uuid import UUID

from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2_000)


class CitationResponse(BaseModel):
    number: int
    chunk_id: UUID
    page_number: int
    quote: str
    start_char: int
    end_char: int


class AnswerResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
    answer_mode: str
    retrieval_mode: str
    grounded: bool
    disclaimer: str
