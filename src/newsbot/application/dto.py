from __future__ import annotations

from pydantic import BaseModel, Field


class ArticleContext(BaseModel):
    source_name: str
    title: str
    summary: str | None = None
    url: str


class StoryContext(BaseModel):
    canonical_title: str
    summary: str
    source_count: int
    source_names: list[str]
    category_hint: str | None = None


class ImportanceResult(BaseModel):
    importance_score: float = Field(ge=0.0, le=1.0)
    category: str
    is_breaking: bool
    reasoning: str


class VerificationResult(BaseModel):
    same_event: bool
    confidence_adjustment: float = Field(ge=-1.0, le=1.0)
    reasoning: str


class TweetDraftResult(BaseModel):
    text: str
    style: str
    thread_recommended: bool
    reasoning: str = ""


class CouncilVoteResult(BaseModel):
    approve: bool
    reasoning: str
