from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class StoryOut(BaseModel):
    id: UUID
    canonical_title: str
    summary: str
    source_count: int
    confidence_score: float
    importance_score: float
    status: str
    is_breaking: bool
    category: str | None


class TweetOut(BaseModel):
    id: UUID
    story_id: UUID
    tweet_text: str
    tweet_style: str | None
    is_dry_run: bool
    status: str
    x_tweet_id: str | None
    posted_at: datetime | None
    failure_reason: str | None


class RejectionOut(BaseModel):
    stage: str
    reason_code: str
    story_id: UUID | None
    raw_article_id: UUID | None
    detail: str | None
    created_at: datetime


class ConfigOut(BaseModel):
    env: str
    dry_run: bool
    llm_provider: str
    confidence_threshold: float
    importance_threshold: float
    research_importance_threshold: float
    pending_story_max_age_hours: int
    max_story_age_for_posting_hours: int
    dedup_similarity_threshold: float
    breaking_confidence_threshold: float
    max_tweets_per_day: int
    min_post_interval_minutes: int
    min_breaking_interval_minutes: int
    poll_interval_minutes: int
    max_article_age_days: int
    max_articles_per_source_per_poll: int
    max_stories_per_cycle: int
    llm_call_delay_seconds: float
    source_poll_delay_seconds: float
    enable_story_council: bool
    council_approval_threshold: float
    council_max_candidates_per_cycle: int


class CouncilVoteOut(BaseModel):
    id: UUID
    story_id: UUID
    persona_name: str
    approve: bool
    reasoning: str
    created_at: datetime
