from datetime import datetime, timezone
from enum import Enum, auto

import structlog

from newsbot.application.interfaces.repositories import (
    ArticleRepository,
    RejectionRepository,
    SourceRepository,
    StoryRepository,
)
from newsbot.application.services.dedup_service import DedupService
from newsbot.application.services.gating_service import GatingService
from newsbot.application.services.importance_service import ImportanceService
from newsbot.application.services.ingestion_service import IngestionService
from newsbot.application.services.posting_service import PostingService
from newsbot.application.services.story_council_service import StoryCouncilService
from newsbot.application.services.tweet_generation_service import TweetGenerationService
from newsbot.application.services.verification_service import VerificationService
from newsbot.domain.enums import RejectionReason, RejectionStage, StoryStatus
from newsbot.domain.models import RejectionRecord, Story

logger = structlog.get_logger(__name__)


class PostAttemptResult(Enum):
    POSTED = auto()
    GATED = auto()
    COUNCIL_REJECTED = auto()
    STALE_REJECTED = auto()


class PipelineOrchestrator:
    def __init__(
        self,
        ingestion_service: IngestionService,
        dedup_service: DedupService,
        verification_service: VerificationService,
        importance_service: ImportanceService,
        gating_service: GatingService,
        tweet_generation_service: TweetGenerationService,
        posting_service: PostingService,
        story_repo: StoryRepository,
        article_repo: ArticleRepository,
        source_repo: SourceRepository,
        rejection_repo: RejectionRepository,
        breaking_confidence_threshold: float,
        story_council_service: StoryCouncilService | None = None,
        enable_story_council: bool = False,
        council_max_candidates_per_cycle: int = 3,
        max_story_age_for_posting_hours: int = 24,
        llm_provider: object | None = None,
    ) -> None:
        self._ingestion = ingestion_service
        self._dedup = dedup_service
        self._verification = verification_service
        self._importance = importance_service
        self._gating = gating_service
        self._tweet_generation = tweet_generation_service
        self._posting = posting_service
        self._story_repo = story_repo
        self._article_repo = article_repo
        self._source_repo = source_repo
        self._rejection_repo = rejection_repo
        self._breaking_confidence_threshold = breaking_confidence_threshold
        self._story_council = story_council_service
        self._enable_story_council = enable_story_council and story_council_service is not None
        self._council_max_candidates_per_cycle = council_max_candidates_per_cycle
        self._max_story_age_for_posting_hours = max_story_age_for_posting_hours
        self._llm_provider = llm_provider

    async def aclose(self) -> None:
        aclose = getattr(self._llm_provider, "aclose", None)
        if aclose is not None:
            await aclose()

    async def run_poll_cycle(self) -> dict:
        stats = await self._ingestion.poll_all_sources()
        logger.info("poll_cycle_complete", **stats)
        return stats

    async def run_process_cycle(self) -> dict:
        dedup_stats = await self._dedup.cluster_new_articles()
        verification_stats = await self._verification.verify_pending_stories()
        importance_stats = await self._importance.score_verified_stories()

        breaking_stats = await self._post_breaking_stories()

        stats = {
            "dedup": dedup_stats,
            "verification": verification_stats,
            "importance": importance_stats,
            "breaking_posted": breaking_stats,
        }
        logger.info("process_cycle_complete", **stats)
        return stats

    async def _post_breaking_stories(self) -> int:
        approved = await self._story_repo.list_by_status(StoryStatus.APPROVED)
        posted = 0
        for story in approved:
            if not story.is_breaking or story.confidence_score < self._breaking_confidence_threshold:
                continue
            result = await self._try_post_story(story)
            if result == PostAttemptResult.POSTED:
                posted += 1
            # A gate/council rejection on one breaking story doesn't block trying
            # the next one -- breaking candidates are rare by design already.
        return posted

    async def run_posting_window(self, max_stories: int = 1) -> int:
        candidate_limit = max(max_stories, self._council_max_candidates_per_cycle)
        approved = await self._story_repo.list_by_status(StoryStatus.APPROVED, limit=candidate_limit)
        posted = 0
        for story in approved:
            if story.is_breaking:
                continue  # already handled by the breaking fast path
            if posted >= max_stories:
                break
            result = await self._try_post_story(story)
            if result == PostAttemptResult.POSTED:
                posted += 1
            elif result == PostAttemptResult.GATED:
                # Every other candidate would fail the same daily-cap/interval check
                # right now, so trying more would just waste council/LLM calls.
                break
            # COUNCIL_REJECTED / STALE_REJECTED -> fall through, try the next candidate immediately.
        return posted

    async def _try_post_story(self, story: Story) -> PostAttemptResult:
        assert story.id is not None
        story_id = story.id
        gate_decision = await self._gating.check(is_breaking=story.is_breaking)
        if not gate_decision.allowed:
            logger.info("posting_gated", story_id=str(story_id), reason=gate_decision.reason)
            return PostAttemptResult.GATED

        articles = await self._article_repo.list_by_story(story_id)
        source_names = []
        for article in articles:
            source = await self._source_repo.get_by_id(article.source_id)
            source_names.append(source.name if source else "unknown")

        published_dates = [a.published_at for a in articles if a.published_at is not None]
        if published_dates and not story.is_breaking:
            latest_published = max(published_dates)
            age = datetime.now(timezone.utc) - latest_published
            if age.total_seconds() > self._max_story_age_for_posting_hours * 3600:
                await self._rejection_repo.add(
                    RejectionRecord(
                        stage=RejectionStage.STALENESS,
                        reason_code=RejectionReason.STORY_TOO_OLD,
                        story_id=story_id,
                        detail=(
                            f"latest article published_at={latest_published.isoformat()}, "
                            f"exceeds max_story_age_for_posting_hours="
                            f"{self._max_story_age_for_posting_hours}"
                        ),
                    )
                )
                await self._story_repo.update_status(story_id, StoryStatus.REJECTED)
                logger.info(
                    "story_rejected_stale",
                    story_id=str(story_id),
                    latest_published_at=latest_published.isoformat(),
                )
                return PostAttemptResult.STALE_REJECTED

        if self._enable_story_council and self._story_council is not None:
            verdict = await self._story_council.review(story, source_names)
            if not verdict.approved:
                await self._rejection_repo.add(
                    RejectionRecord(
                        stage=RejectionStage.COUNCIL,
                        reason_code=RejectionReason.COUNCIL_REJECTED,
                        story_id=story_id,
                        detail="; ".join(
                            f"{v.persona_name}={'yes' if v.approve else 'no'}: {v.reasoning}"
                            for v in verdict.votes
                        )
                        or "all council members failed to respond",
                    )
                )
                await self._story_repo.update_status(story_id, StoryStatus.REJECTED)
                logger.info("story_council_rejected", story_id=str(story_id))
                return PostAttemptResult.COUNCIL_REJECTED

        draft = await self._tweet_generation.generate(story, source_names)
        await self._posting.post(story_id, draft)
        await self._story_repo.update_status(story_id, StoryStatus.POSTED)
        return PostAttemptResult.POSTED
