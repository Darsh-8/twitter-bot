import asyncio

import structlog

from newsbot.application.dto import StoryContext
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

DEFAULT_MAX_STORIES_PER_CYCLE = 20
DEFAULT_LLM_CALL_DELAY_SECONDS = 3.0


class ImportanceService:
    def __init__(
        self,
        story_repo: StoryRepository,
        article_repo: ArticleRepository,
        source_repo: SourceRepository,
        rejection_repo: RejectionRepository,
        llm: LLMProvider,
        importance_threshold: float,
        max_stories_per_cycle: int = DEFAULT_MAX_STORIES_PER_CYCLE,
        llm_call_delay_seconds: float = DEFAULT_LLM_CALL_DELAY_SECONDS,
        research_importance_threshold: float | None = None,
    ) -> None:
        self._story_repo = story_repo
        self._article_repo = article_repo
        self._source_repo = source_repo
        self._rejection_repo = rejection_repo
        self._llm = llm
        self._importance_threshold = importance_threshold
        self._max_stories_per_cycle = max_stories_per_cycle
        self._llm_call_delay_seconds = llm_call_delay_seconds
        self._research_importance_threshold = (
            research_importance_threshold if research_importance_threshold is not None else importance_threshold
        )

    async def score_verified_stories(self) -> dict:
        stories = await self._story_repo.list_by_status(
            StoryStatus.VERIFIED, limit=self._max_stories_per_cycle
        )
        stats = {"approved": 0, "rejected": 0, "skipped_llm_error": 0}
        for story in stories:
            assert story.id is not None
            story_id = story.id
            articles = await self._article_repo.list_by_story(story_id)
            source_names = []
            for article in articles:
                source = await self._source_repo.get_by_id(article.source_id)
                source_names.append(source.name if source else "unknown")

            context = StoryContext(
                canonical_title=story.canonical_title,
                summary=story.summary,
                source_count=story.source_count,
                source_names=source_names,
            )
            try:
                result = await self._llm.score_importance(context)
            except LLMProviderError as exc:
                logger.warning(
                    "story_importance_llm_error",
                    story_id=str(story_id),
                    error=str(exc),
                    retryable=exc.retryable,
                )
                if not exc.retryable:
                    await self._rejection_repo.add(
                        RejectionRecord(
                            stage=RejectionStage.IMPORTANCE,
                            reason_code=RejectionReason.LLM_REFUSED,
                            story_id=story_id,
                            detail=str(exc),
                        )
                    )
                stats["skipped_llm_error"] += 1
                continue
            await asyncio.sleep(self._llm_call_delay_seconds)
            await self._story_repo.update_scores(story_id, importance_score=result.importance_score)
            await self._story_repo.set_breaking(story_id, result.is_breaking)
            await self._story_repo.set_category(story_id, result.category)

            effective_threshold = (
                self._research_importance_threshold
                if "research" in result.category.lower()
                else self._importance_threshold
            )
            if result.importance_score >= effective_threshold:
                await self._story_repo.update_status(story_id, StoryStatus.APPROVED)
                stats["approved"] += 1
            else:
                await self._story_repo.update_status(story_id, StoryStatus.REJECTED)
                await self._rejection_repo.add(
                    RejectionRecord(
                        stage=RejectionStage.IMPORTANCE,
                        reason_code=RejectionReason.LOW_IMPORTANCE,
                        story_id=story_id,
                        detail=f"importance={result.importance_score:.2f} category={result.category} "
                        f"threshold={effective_threshold:.2f}",
                    )
                )
                stats["rejected"] += 1
            logger.info(
                "story_scored",
                story_id=str(story_id),
                importance=result.importance_score,
                is_breaking=result.is_breaking,
                category=result.category,
            )
        return stats
