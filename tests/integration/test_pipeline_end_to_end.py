from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import respx

from newsbot.adapters.social.dry_run_client import DryRunXClient
from newsbot.adapters.sources.rss_client import RSSSourceClient
from newsbot.application.services.dedup_service import DedupService
from newsbot.application.services.gating_service import GatingService
from newsbot.application.services.importance_service import ImportanceService
from newsbot.application.services.ingestion_service import IngestionService
from newsbot.application.services.pipeline_orchestrator import PipelineOrchestrator
from newsbot.application.services.posting_service import PostingService
from newsbot.application.services.tweet_generation_service import TweetGenerationService
from newsbot.application.services.verification_service import VerificationService
from newsbot.domain.enums import TweetStatus
from newsbot.domain.models import Source
from tests.integration.fakes import (
    FakeEmbedder,
    FakeLLMProvider,
    InMemoryArticleRepository,
    InMemoryRejectionRepository,
    InMemorySourceRepository,
    InMemoryStoryRepository,
    InMemoryTweetRepository,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "sample_feeds"

SOURCE_A_URL = "https://source-a.example.com/feed.xml"
SOURCE_B_URL = "https://source-b.example.com/feed.xml"
SOURCE_C_URL = "https://source-c.example.com/feed.xml"


def _build_pipeline():
    source_a = Source(id=uuid4(), name="Source A", source_type="rss", url=SOURCE_A_URL, category="tech_media", trust_weight=0.7)
    source_b = Source(id=uuid4(), name="Source B", source_type="rss", url=SOURCE_B_URL, category="tech_media", trust_weight=0.7)

    source_repo = InMemorySourceRepository([source_a, source_b])
    article_repo = InMemoryArticleRepository()
    story_repo = InMemoryStoryRepository()
    tweet_repo = InMemoryTweetRepository()
    rejection_repo = InMemoryRejectionRepository()

    embedder = FakeEmbedder()
    llm = FakeLLMProvider()
    rss_client = RSSSourceClient()
    social_client = DryRunXClient()

    ingestion_service = IngestionService(source_repo, article_repo, rss_client, embedder)
    dedup_service = DedupService(article_repo, story_repo, similarity_threshold=0.6)
    verification_service = VerificationService(
        story_repo,
        article_repo,
        source_repo,
        rejection_repo,
        llm,
        confidence_threshold=0.6,
        llm_call_delay_seconds=0,
    )
    importance_service = ImportanceService(
        story_repo,
        article_repo,
        source_repo,
        rejection_repo,
        llm,
        importance_threshold=0.55,
        llm_call_delay_seconds=0,
    )
    gating_service = GatingService(
        tweet_repo, max_tweets_per_day=8, min_post_interval_minutes=45, min_breaking_interval_minutes=10
    )
    tweet_generation_service = TweetGenerationService(llm)
    posting_service = PostingService(tweet_repo, social_client)

    orchestrator = PipelineOrchestrator(
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
        breaking_confidence_threshold=0.4,
    )
    return orchestrator, story_repo, tweet_repo, rejection_repo


@pytest.mark.asyncio
@respx.mock
async def test_overlapping_stories_from_two_sources_merge_and_get_dry_run_posted():
    respx.get(SOURCE_A_URL).mock(
        return_value=httpx.Response(200, content=(FIXTURES_DIR / "source_a.xml").read_bytes())
    )
    respx.get(SOURCE_B_URL).mock(
        return_value=httpx.Response(200, content=(FIXTURES_DIR / "source_b.xml").read_bytes())
    )

    orchestrator, story_repo, tweet_repo, rejection_repo = _build_pipeline()

    poll_stats = await orchestrator.run_poll_cycle()
    assert poll_stats["articles_new"] == 2

    process_stats = await orchestrator.run_process_cycle()
    assert process_stats["dedup"]["merged_new_cluster"] == 1
    assert process_stats["verification"]["verified"] == 1
    assert process_stats["importance"]["approved"] == 1
    # story is flagged breaking by the fake LLM and clears the breaking confidence bar,
    # so it's posted immediately during run_process_cycle rather than waiting for a posting window
    assert process_stats["breaking_posted"] == 1

    assert len(tweet_repo.tweets) == 1
    tweet = tweet_repo.tweets[0]
    assert tweet.status == TweetStatus.DRY_RUN_POSTED
    assert tweet.is_dry_run is True
    assert "GPT-6" in tweet.tweet_text

    assert not rejection_repo.rejections
