from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from newsbot.domain.enums import (
    RejectionReason,
    RejectionStage,
    StoryStatus,
    TweetStatus,
)
from newsbot.domain.value_objects import EmbeddingVector


@dataclass(slots=True)
class Source:
    id: UUID
    name: str
    source_type: str
    url: str
    category: str
    trust_weight: float = 1.0
    is_active: bool = True
    last_polled_at: datetime | None = None


@dataclass(slots=True)
class Article:
    id: UUID | None
    source_id: UUID
    external_id: str
    title: str
    url: str
    summary: str | None = None
    content: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime | None = None
    embedding: EmbeddingVector | None = None
    story_id: UUID | None = None
    raw_payload: dict | None = None


@dataclass(slots=True)
class Story:
    id: UUID | None
    canonical_title: str
    summary: str
    embedding: EmbeddingVector | None = None
    source_count: int = 1
    confidence_score: float = 0.0
    importance_score: float = 0.0
    status: StoryStatus = StoryStatus.PENDING
    is_breaking: bool = False
    category: str | None = None
    first_seen_at: datetime | None = None
    last_updated_at: datetime | None = None


@dataclass(slots=True)
class TweetDraft:
    text: str
    style: str
    thread_recommended: bool
    reasoning: str = ""
    image_url: str | None = None


@dataclass(slots=True)
class PostedTweet:
    id: UUID | None
    story_id: UUID
    tweet_text: str
    tweet_style: str | None
    is_dry_run: bool
    status: TweetStatus
    x_tweet_id: str | None = None
    posted_at: datetime | None = None
    failure_reason: str | None = None
    retry_count: int = 0


@dataclass(slots=True)
class RejectionRecord:
    stage: RejectionStage
    reason_code: RejectionReason
    story_id: UUID | None = None
    raw_article_id: UUID | None = None
    detail: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now())


@dataclass(slots=True)
class CouncilVoteRecord:
    story_id: UUID
    persona_name: str
    approve: bool
    reasoning: str
    id: UUID | None = None
    created_at: datetime | None = None
