from uuid import uuid4

import pytest

from newsbot.application.dto import ImportanceResult
from newsbot.application.interfaces.llm_provider import LLMProviderError
from newsbot.application.services.importance_service import ImportanceService
from newsbot.domain.enums import StoryStatus
from newsbot.domain.models import Story


class FakeArticleRepository:
    async def list_by_story(self, story_id):
        return []


class FakeSourceRepository:
    async def get_by_id(self, source_id):
        return None


class FakeStoryRepository:
    def __init__(self, stories):
        self._stories = stories
        self.statuses = {}
        self.scores = {}
        self.breaking = {}
        self.categories = {}

    async def list_by_status(self, status, limit=50):
        return [s for s in self._stories if s.status == status]

    async def update_scores(self, story_id, confidence_score=None, importance_score=None):
        if importance_score is not None:
            self.scores[story_id] = importance_score

    async def set_breaking(self, story_id, is_breaking):
        self.breaking[story_id] = is_breaking

    async def set_category(self, story_id, category):
        self.categories[story_id] = category

    async def update_status(self, story_id, status):
        self.statuses[story_id] = status


class FakeRejectionRepository:
    def __init__(self):
        self.rejections = []

    async def add(self, rejection):
        self.rejections.append(rejection)


class FakeLLM:
    def __init__(self, result: ImportanceResult):
        self._result = result

    async def score_importance(self, story):
        return self._result


def _story(status):
    return Story(id=uuid4(), canonical_title="Title", summary="Summary", status=status)


@pytest.mark.asyncio
async def test_story_above_threshold_is_approved():
    story = _story(StoryStatus.VERIFIED)
    story_repo = FakeStoryRepository([story])
    rejection_repo = FakeRejectionRepository()
    service = ImportanceService(
        story_repo=story_repo,
        article_repo=FakeArticleRepository(),
        source_repo=FakeSourceRepository(),
        rejection_repo=rejection_repo,
        llm=FakeLLM(ImportanceResult(importance_score=0.9, category="model_release", is_breaking=True, reasoning="")),
        importance_threshold=0.55,
        llm_call_delay_seconds=0,
    )
    stats = await service.score_verified_stories()
    assert stats == {"approved": 1, "rejected": 0, "skipped_llm_error": 0}
    assert story_repo.statuses[story.id] == StoryStatus.APPROVED
    assert story_repo.breaking[story.id] is True
    assert not rejection_repo.rejections


@pytest.mark.asyncio
async def test_story_below_threshold_is_rejected_and_logged():
    story = _story(StoryStatus.VERIFIED)
    story_repo = FakeStoryRepository([story])
    rejection_repo = FakeRejectionRepository()
    service = ImportanceService(
        story_repo=story_repo,
        article_repo=FakeArticleRepository(),
        source_repo=FakeSourceRepository(),
        rejection_repo=rejection_repo,
        llm=FakeLLM(ImportanceResult(importance_score=0.2, category="minor_update", is_breaking=False, reasoning="")),
        importance_threshold=0.55,
        llm_call_delay_seconds=0,
    )
    stats = await service.score_verified_stories()
    assert stats == {"approved": 0, "rejected": 1, "skipped_llm_error": 0}
    assert story_repo.statuses[story.id] == StoryStatus.REJECTED
    assert len(rejection_repo.rejections) == 1


@pytest.mark.asyncio
async def test_research_category_uses_higher_threshold():
    story = _story(StoryStatus.VERIFIED)
    story_repo = FakeStoryRepository([story])
    rejection_repo = FakeRejectionRepository()
    service = ImportanceService(
        story_repo=story_repo,
        article_repo=FakeArticleRepository(),
        source_repo=FakeSourceRepository(),
        rejection_repo=rejection_repo,
        llm=FakeLLM(ImportanceResult(importance_score=0.65, category="research", is_breaking=False, reasoning="")),
        importance_threshold=0.55,
        llm_call_delay_seconds=0,
        research_importance_threshold=0.75,
    )
    stats = await service.score_verified_stories()
    assert stats == {"approved": 0, "rejected": 1, "skipped_llm_error": 0}
    assert story_repo.statuses[story.id] == StoryStatus.REJECTED


@pytest.mark.asyncio
async def test_non_research_category_uses_normal_threshold_at_same_score():
    story = _story(StoryStatus.VERIFIED)
    story_repo = FakeStoryRepository([story])
    rejection_repo = FakeRejectionRepository()
    service = ImportanceService(
        story_repo=story_repo,
        article_repo=FakeArticleRepository(),
        source_repo=FakeSourceRepository(),
        rejection_repo=rejection_repo,
        llm=FakeLLM(ImportanceResult(importance_score=0.65, category="model_release", is_breaking=False, reasoning="")),
        importance_threshold=0.55,
        llm_call_delay_seconds=0,
        research_importance_threshold=0.75,
    )
    stats = await service.score_verified_stories()
    assert stats == {"approved": 1, "rejected": 0, "skipped_llm_error": 0}
    assert story_repo.statuses[story.id] == StoryStatus.APPROVED


class FailingLLM:
    def __init__(self, error: LLMProviderError):
        self._error = error

    async def score_importance(self, story):
        raise self._error


@pytest.mark.asyncio
async def test_retryable_llm_error_skips_story_without_rejecting():
    story = _story(StoryStatus.VERIFIED)
    story_repo = FakeStoryRepository([story])
    rejection_repo = FakeRejectionRepository()
    service = ImportanceService(
        story_repo=story_repo,
        article_repo=FakeArticleRepository(),
        source_repo=FakeSourceRepository(),
        rejection_repo=rejection_repo,
        llm=FailingLLM(LLMProviderError("malformed response", retryable=True)),
        importance_threshold=0.55,
        llm_call_delay_seconds=0,
    )
    stats = await service.score_verified_stories()
    assert stats == {"approved": 0, "rejected": 0, "skipped_llm_error": 1}
    assert story.id not in story_repo.statuses
    assert not rejection_repo.rejections


@pytest.mark.asyncio
async def test_non_retryable_llm_error_rejects_story():
    story = _story(StoryStatus.VERIFIED)
    story_repo = FakeStoryRepository([story])
    rejection_repo = FakeRejectionRepository()
    service = ImportanceService(
        story_repo=story_repo,
        article_repo=FakeArticleRepository(),
        source_repo=FakeSourceRepository(),
        rejection_repo=rejection_repo,
        llm=FailingLLM(LLMProviderError("no content", retryable=False)),
        importance_threshold=0.55,
        llm_call_delay_seconds=0,
    )
    stats = await service.score_verified_stories()
    assert stats == {"approved": 0, "rejected": 0, "skipped_llm_error": 1}
    assert len(rejection_repo.rejections) == 1
