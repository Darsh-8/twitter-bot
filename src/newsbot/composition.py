"""Composition root: wires adapters into services given a DB session and settings."""

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.adapters.embeddings.sentence_transformer_embedder import SentenceTransformerEmbedder
from newsbot.adapters.llm.base import COUNCIL_PERSONAS
from newsbot.adapters.llm.factory import get_llm_provider
from newsbot.adapters.persistence.article_repository import SqlArticleRepository
from newsbot.adapters.persistence.council_vote_repository import SqlCouncilVoteRepository
from newsbot.adapters.persistence.rejection_repository import SqlRejectionRepository
from newsbot.adapters.persistence.source_repository import SqlSourceRepository
from newsbot.adapters.persistence.story_repository import SqlStoryRepository
from newsbot.adapters.persistence.tweet_repository import SqlTweetRepository
from newsbot.adapters.social.factory import get_social_client
from newsbot.adapters.sources.rss_client import RSSSourceClient
from newsbot.application.services.dedup_service import DedupService
from newsbot.application.services.gating_service import GatingService
from newsbot.application.services.importance_service import ImportanceService
from newsbot.application.services.ingestion_service import IngestionService
from newsbot.application.services.pipeline_orchestrator import PipelineOrchestrator
from newsbot.application.services.posting_service import PostingService
from newsbot.application.services.story_council_service import StoryCouncilService
from newsbot.application.services.tweet_generation_service import TweetGenerationService
from newsbot.application.services.verification_service import VerificationService
from newsbot.config.settings import Settings, get_settings


@lru_cache
def _embedder(model_name: str) -> SentenceTransformerEmbedder:
    return SentenceTransformerEmbedder(model_name)


def build_orchestrator(session: AsyncSession, settings: Settings | None = None) -> PipelineOrchestrator:
    settings = settings or get_settings()

    source_repo = SqlSourceRepository(session)
    article_repo = SqlArticleRepository(session)
    story_repo = SqlStoryRepository(session)
    tweet_repo = SqlTweetRepository(session)
    rejection_repo = SqlRejectionRepository(session)
    council_vote_repo = SqlCouncilVoteRepository(session)

    embedder = _embedder(settings.embedding_model_name)
    llm = get_llm_provider(settings)
    social_client = get_social_client(settings)
    rss_client = RSSSourceClient()

    ingestion_service = IngestionService(
        source_repo,
        article_repo,
        rss_client,
        embedder,
        settings.max_article_age_days,
        settings.max_articles_per_source_per_poll,
        settings.source_poll_delay_seconds,
    )
    dedup_service = DedupService(article_repo, story_repo, settings.dedup_similarity_threshold)
    verification_service = VerificationService(
        story_repo,
        article_repo,
        source_repo,
        rejection_repo,
        llm,
        settings.confidence_threshold,
        settings.max_stories_per_cycle,
        settings.llm_call_delay_seconds,
        settings.pending_story_max_age_hours,
    )
    importance_service = ImportanceService(
        story_repo,
        article_repo,
        source_repo,
        rejection_repo,
        llm,
        settings.importance_threshold,
        settings.max_stories_per_cycle,
        settings.llm_call_delay_seconds,
        settings.research_importance_threshold,
    )
    gating_service = GatingService(
        tweet_repo,
        settings.max_tweets_per_day,
        settings.min_post_interval_minutes,
        settings.min_breaking_interval_minutes,
    )
    tweet_generation_service = TweetGenerationService(llm)
    posting_service = PostingService(tweet_repo, social_client)
    story_council_service = StoryCouncilService(
        llm,
        council_vote_repo,
        COUNCIL_PERSONAS,
        settings.council_approval_threshold,
        settings.llm_call_delay_seconds,
    )

    return PipelineOrchestrator(
        ingestion_service=ingestion_service,
        dedup_service=dedup_service,
        verification_service=verification_service,
        importance_service=importance_service,
        gating_service=gating_service,
        tweet_generation_service=tweet_generation_service,
        posting_service=posting_service,
        story_repo=story_repo,
        article_repo=article_repo,
        source_repo=source_repo,
        rejection_repo=rejection_repo,
        breaking_confidence_threshold=settings.breaking_confidence_threshold,
        story_council_service=story_council_service,
        enable_story_council=settings.enable_story_council,
        council_max_candidates_per_cycle=settings.council_max_candidates_per_cycle,
        max_story_age_for_posting_hours=settings.max_story_age_for_posting_hours,
    )
