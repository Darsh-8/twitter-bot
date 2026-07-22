from fastapi import APIRouter

from newsbot.api.schemas import ConfigOut
from newsbot.config.settings import get_settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=ConfigOut)
async def get_config() -> ConfigOut:
    settings = get_settings()
    return ConfigOut(
        env=settings.env,
        dry_run=settings.dry_run,
        llm_provider=settings.llm_provider,
        confidence_threshold=settings.confidence_threshold,
        importance_threshold=settings.importance_threshold,
        research_importance_threshold=settings.research_importance_threshold,
        pending_story_max_age_hours=settings.pending_story_max_age_hours,
        max_story_age_for_posting_hours=settings.max_story_age_for_posting_hours,
        dedup_similarity_threshold=settings.dedup_similarity_threshold,
        breaking_confidence_threshold=settings.breaking_confidence_threshold,
        max_tweets_per_day=settings.max_tweets_per_day,
        min_post_interval_minutes=settings.min_post_interval_minutes,
        min_breaking_interval_minutes=settings.min_breaking_interval_minutes,
        poll_interval_minutes=settings.poll_interval_minutes,
        max_article_age_days=settings.max_article_age_days,
        max_articles_per_source_per_poll=settings.max_articles_per_source_per_poll,
        max_stories_per_cycle=settings.max_stories_per_cycle,
        llm_call_delay_seconds=settings.llm_call_delay_seconds,
        source_poll_delay_seconds=settings.source_poll_delay_seconds,
        enable_story_council=settings.enable_story_council,
        council_approval_threshold=settings.council_approval_threshold,
        council_max_candidates_per_cycle=settings.council_max_candidates_per_cycle,
    )
