from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, Field

from tenderlens.retrieval.service import RetrievalHit


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    hit: RetrievalHit


class DraftClaim(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)
    evidence_id: str = Field(pattern=r"^C[1-9][0-9]*$")
    quote: str = Field(min_length=1, max_length=2_000)


class AnswerDraft(BaseModel):
    cannot_answer: bool
    claims: list[DraftClaim] = Field(max_length=10)


@dataclass(frozen=True, slots=True)
class VerifiedCitation:
    number: int
    chunk_id: UUID
    page_number: int
    quote: str
    start_char: int
    end_char: int


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    answer: str
    citations: list[VerifiedCitation]
    answer_mode: str
    retrieval_mode: str
    grounded: bool
    disclaimer: str
