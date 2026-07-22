from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from newsbot.application.dto import VerificationResult
from newsbot.application.services.verification_service import VerificationService
from newsbot.domain.enums import StoryStatus
from newsbot.domain.models import Article, Source, Story


class FakeArticleRepository:
    def __init__(self, articles: list[Article]):
        self._articles = articles

    async def list_by_story(self, story_id):
        return self._articles


class FakeSourceRepository:
    def __init__(self, sources: dict):
        self._sources = sources

    async def get_by_id(self, source_id):
        return self._sources.get(source_id)


class FakeStoryRepository:
    def __init__(self):
        self.updated_scores = {}

    async def update_scores(self, story_id, confidence_score=None, importance_score=None):
        self.updated_scores[story_id] = confidence_score


class FakeRejectionRepository:
    async def add(self, rejection):
        return rejection


class FakeLLM:
    def __init__(self, result: VerificationResult):
        self._result = result

    async def verify_corroboration(self, articles):
        return self._result


def _make_article(source_id):
    return Article(
        id=uuid4(),
        source_id=source_id,
        external_id="abc",
        title="Some AI news",
        url="https://example.com",
        summary="summary",
    )


@pytest.mark.asyncio
async def test_multi_source_story_gets_high_confidence():
    source_a, source_b = uuid4(), uuid4()
    articles = [_make_article(source_a), _make_article(source_b)]
    sources = {
        source_a: Source(id=source_a, name="A", source_type="rss", url="", category="tech_media", trust_weight=0.7),
        source_b: Source(id=source_b, name="B", source_type="rss", url="", category="tech_media", trust_weight=0.7),
    }
    service = VerificationService(
        story_repo=FakeStoryRepository(),
        article_repo=FakeArticleRepository(articles),
        source_repo=FakeSourceRepository(sources),
        rejection_repo=FakeRejectionRepository(),
        llm=FakeLLM(VerificationResult(same_event=True, confidence_adjustment=0.0, reasoning="")),
        confidence_threshold=0.6,
        llm_call_delay_seconds=0,
    )
    confidence = await service._verify_story(uuid4())
    assert confidence >= 0.6


@pytest.mark.asyncio
async def test_single_high_trust_source_is_confident_without_llm_call():
    source_id = uuid4()
    articles = [_make_article(source_id)]
    sources = {
        source_id: Source(id=source_id, name="OpenAI Blog", source_type="rss", url="", category="lab_official", trust_weight=1.0)
    }

    class ExplodingLLM:
        async def verify_corroboration(self, articles):
            raise AssertionError("LLM should not be called for a high-trust single source")

    service = VerificationService(
        story_repo=FakeStoryRepository(),
        article_repo=FakeArticleRepository(articles),
        source_repo=FakeSourceRepository(sources),
        rejection_repo=FakeRejectionRepository(),
        llm=ExplodingLLM(),
        confidence_threshold=0.6,
        llm_call_delay_seconds=0,
    )
    confidence = await service._verify_story(uuid4())
    assert confidence >= 0.6


@pytest.mark.asyncio
async def test_single_low_trust_source_falls_below_threshold_when_llm_disagrees():
    source_id = uuid4()
    articles = [_make_article(source_id)]
    sources = {
        source_id: Source(id=source_id, name="Random Blog", source_type="rss", url="", category="tech_media", trust_weight=0.3)
    }
    service = VerificationService(
        story_repo=FakeStoryRepository(),
        article_repo=FakeArticleRepository(articles),
        source_repo=FakeSourceRepository(sources),
        rejection_repo=FakeRejectionRepository(),
        llm=FakeLLM(VerificationResult(same_event=False, confidence_adjustment=-0.2, reasoning="unrelated")),
        confidence_threshold=0.6,
        llm_call_delay_seconds=0,
    )
    confidence = await service._verify_story(uuid4())
    assert confidence < 0.6


class FullFakeStoryRepository:
    def __init__(self, stories: list[Story]):
        self._stories = stories
        self.updated_scores = {}
        self.statuses = {}

    async def list_by_status(self, status, limit=50):
        return [s for s in self._stories if s.status == status]

    async def update_scores(self, story_id, confidence_score=None, importance_score=None):
        self.updated_scores[story_id] = confidence_score

    async def update_status(self, story_id, status):
        self.statuses[story_id] = status


def _pending_story(age_hours: float) -> Story:
    return Story(
        id=uuid4(),
        canonical_title="Some story",
        summary="summary",
        status=StoryStatus.PENDING,
        first_seen_at=datetime.now(timezone.utc) - timedelta(hours=age_hours),
    )


@pytest.mark.asyncio
async def test_stale_low_confidence_story_is_rejected_terminally():
    story = _pending_story(age_hours=72)
    source_id = uuid4()
    sources = {
        source_id: Source(id=source_id, name="Random Blog", source_type="rss", url="", category="tech_media", trust_weight=0.3)
    }
    story_repo = FullFakeStoryRepository([story])
    service = VerificationService(
        story_repo=story_repo,
        article_repo=FakeArticleRepository([_make_article(source_id)]),
        source_repo=FakeSourceRepository(sources),
        rejection_repo=FakeRejectionRepository(),
        llm=FakeLLM(VerificationResult(same_event=False, confidence_adjustment=-0.2, reasoning="unrelated")),
        confidence_threshold=0.6,
        llm_call_delay_seconds=0,
        pending_story_max_age_hours=48,
    )
    stats = await service.verify_pending_stories()
    assert stats["expired"] == 1
    assert stats["rejected"] == 0
    assert story_repo.statuses[story.id] == StoryStatus.REJECTED


@pytest.mark.asyncio
async def test_fresh_low_confidence_story_stays_pending():
    story = _pending_story(age_hours=1)
    source_id = uuid4()
    sources = {
        source_id: Source(id=source_id, name="Random Blog", source_type="rss", url="", category="tech_media", trust_weight=0.3)
    }
    story_repo = FullFakeStoryRepository([story])
    service = VerificationService(
        story_repo=story_repo,
        article_repo=FakeArticleRepository([_make_article(source_id)]),
        source_repo=FakeSourceRepository(sources),
        rejection_repo=FakeRejectionRepository(),
        llm=FakeLLM(VerificationResult(same_event=False, confidence_adjustment=-0.2, reasoning="unrelated")),
        confidence_threshold=0.6,
        llm_call_delay_seconds=0,
        pending_story_max_age_hours=48,
    )
    stats = await service.verify_pending_stories()
    assert stats["rejected"] == 1
    assert stats["expired"] == 0
    assert story.id not in story_repo.statuses
