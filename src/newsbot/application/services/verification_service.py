import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog

from newsbot.application.dto import ArticleContext
from newsbot.application.interfaces.llm_provider import LLMProvider, LLMProviderError
from newsbot.application.interfaces.repositories import (
    ArticleRepository,
    RejectionRepository,
    SourceRepository,
    StoryRepository,
)
from newsbot.domain.enums import RejectionReason, RejectionStage, StoryStatus
from newsbot.domain.models import RejectionRecord

logger = structlog.get_logger(__name__)

# Below this combined trust weight, a single-source story needs LLM corroboration
# before it can be trusted; above it, an official/high-trust source is enough alone.
SINGLE_SOURCE_TRUST_CUTOFF = 0.9
DEFAULT_MAX_STORIES_PER_CYCLE = 20
DEFAULT_LLM_CALL_DELAY_SECONDS = 3.0
DEFAULT_PENDING_STORY_MAX_AGE_HOURS = 48


class VerificationService:
    def __init__(
        self,
        story_repo: StoryRepository,
        article_repo: ArticleRepository,
        source_repo: SourceRepository,
        rejection_repo: RejectionRepository,
        llm: LLMProvider,
        confidence_threshold: float,
        max_stories_per_cycle: int = DEFAULT_MAX_STORIES_PER_CYCLE,
        llm_call_delay_seconds: float = DEFAULT_LLM_CALL_DELAY_SECONDS,
        pending_story_max_age_hours: int = DEFAULT_PENDING_STORY_MAX_AGE_HOURS,
    ) -> None:
        self._story_repo = story_repo
        self._article_repo = article_repo
        self._source_repo = source_repo
        self._rejection_repo = rejection_repo
        self._llm = llm
        self._confidence_threshold = confidence_threshold
        self._max_stories_per_cycle = max_stories_per_cycle
        self._llm_call_delay_seconds = llm_call_delay_seconds
        self._pending_story_max_age_hours = pending_story_max_age_hours

    async def verify_pending_stories(self) -> dict:
        stories = await self._story_repo.list_by_status(
            StoryStatus.PENDING, limit=self._max_stories_per_cycle
        )
        stats = {"verified": 0, "rejected": 0, "expired": 0, "skipped_llm_error": 0}
        for story in stories:
            assert story.id is not None
            story_id = story.id
            try:
                confidence = await self._verify_story(story_id)
            except LLMProviderError as exc:
                logger.warning(
                    "story_verification_llm_error",
                    story_id=str(story_id),
                    error=str(exc),
                    retryable=exc.retryable,
                )
                if not exc.retryable:
                    await self._rejection_repo.add(
                        RejectionRecord(
                            stage=RejectionStage.VERIFICATION,
                            reason_code=RejectionReason.LLM_REFUSED,
                            story_id=story_id,
                            detail=str(exc),
                        )
                    )
                stats["skipped_llm_error"] += 1
                continue
            if confidence >= self._confidence_threshold:
                await self._story_repo.update_status(story_id, StoryStatus.VERIFIED)
                stats["verified"] += 1
            else:
                is_expired = story.first_seen_at is not None and (
                    datetime.now(timezone.utc) - story.first_seen_at
                    > timedelta(hours=self._pending_story_max_age_hours)
                )
                await self._rejection_repo.add(
                    RejectionRecord(
                        stage=RejectionStage.VERIFICATION,
                        reason_code=RejectionReason.LOW_CONFIDENCE,
                        story_id=story_id,
                        detail=f"confidence={confidence:.2f} expired={is_expired}",
                    )
                )
                if is_expired:
                    # Never gained enough corroboration within the allowed window --
                    # give up permanently instead of re-verifying this via a fresh LLM
                    # call every single cycle forever.
                    await self._story_repo.update_status(story_id, StoryStatus.REJECTED)
                    stats["expired"] += 1
                else:
                    stats["rejected"] += 1
        return stats

    async def _verify_story(self, story_id: UUID) -> float:
        articles = await self._article_repo.list_by_story(story_id)
        if not articles:
            return 0.0

        weights = []
        for article in articles:
            source = await self._source_repo.get_by_id(article.source_id)
            weights.append(source.trust_weight if source else 0.5)
        trust_sum = sum(weights)

        if len(articles) >= 2:
            confidence = min(1.0, 0.4 + 0.15 * len(articles) + 0.1 * trust_sum)
        elif trust_sum >= SINGLE_SOURCE_TRUST_CUTOFF:
            confidence = min(1.0, 0.55 + 0.3 * trust_sum)
        else:
            article_contexts = [
                ArticleContext(
                    source_name=str(article.source_id),
                    title=article.title,
                    summary=article.summary,
                    url=article.url,
                )
                for article in articles
            ]
            result = await self._llm.verify_corroboration(article_contexts)
            await asyncio.sleep(self._llm_call_delay_seconds)
            base = 0.3 + 0.2 * trust_sum
            confidence = min(1.0, max(0.0, base + result.confidence_adjustment))
            if not result.same_event:
                confidence = min(confidence, 0.3)

        await self._story_repo.update_scores(story_id, confidence_score=confidence)
        logger.info("story_verified", story_id=str(story_id), confidence=confidence, sources=len(articles))
        return confidence
