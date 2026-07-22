from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from newsbot.application.services.gating_service import GateDecision
from newsbot.application.services.pipeline_orchestrator import PipelineOrchestrator
from newsbot.domain.enums import StoryStatus
from newsbot.domain.models import Article, PostedTweet, Story, TweetDraft


class FakeStoryRepository:
    def __init__(self, stories: list[Story]):
        self._stories = stories
        self.statuses: dict = {}

    async def list_by_status(self, status, limit=50):
        return [s for s in self._stories if s.status == status][:limit]

    async def update_status(self, story_id, status):
        self.statuses[story_id] = status
        for s in self._stories:
            if s.id == story_id:
                s.status = status


class FakeArticleRepository:
    def __init__(self, articles_by_story: dict | None = None):
        self._articles_by_story = articles_by_story or {}

    async def list_by_story(self, story_id):
        return self._articles_by_story.get(story_id, [])


class FakeSourceRepository:
    async def get_by_id(self, source_id):
        return None


class FakeRejectionRepository:
    def __init__(self):
        self.rejections = []

    async def add(self, rejection):
        self.rejections.append(rejection)


class FakeGatingService:
    def __init__(self, allowed: bool):
        self._allowed = allowed
        self.calls = 0

    async def check(self, is_breaking):
        self.calls += 1
        return GateDecision(allowed=self._allowed, reason=None if self._allowed else "daily_cap_reached")


@dataclass
class FakeVerdict:
    approved: bool
    votes: list = field(default_factory=list)


class FakeCouncilService:
    def __init__(self, verdicts_by_title: dict):
        self._verdicts_by_title = verdicts_by_title
        self.reviewed_titles = []

    async def review(self, story, source_names):
        self.reviewed_titles.append(story.canonical_title)
        return self._verdicts_by_title[story.canonical_title]


class FakeTweetGenerationService:
    def __init__(self):
        self.generated_for = []

    async def generate(self, story, source_names):
        self.generated_for.append(story.canonical_title)
        return TweetDraft(text="a tweet", style="analytical", thread_recommended=False)


class FakePostingService:
    def __init__(self):
        self.posted = []

    async def post(self, story_id, draft):
        self.posted.append(story_id)
        return PostedTweet(id=None, story_id=story_id, tweet_text=draft.text, tweet_style=draft.style, is_dry_run=True, status="dry_run_posted")


def _approved_story(title: str) -> Story:
    return Story(id=uuid4(), canonical_title=title, summary="s", status=StoryStatus.APPROVED)


def _build_orchestrator(
    stories,
    gating,
    council,
    tweet_gen,
    posting,
    rejection_repo,
    articles_by_story=None,
    max_story_age_for_posting_hours=24,
):
    return PipelineOrchestrator(
        ingestion_service=None,
        dedup_service=None,
        verification_service=None,
        importance_service=None,
        gating_service=gating,
        tweet_generation_service=tweet_gen,
        posting_service=posting,
        story_repo=FakeStoryRepository(stories),
        article_repo=FakeArticleRepository(articles_by_story),
        source_repo=FakeSourceRepository(),
        rejection_repo=rejection_repo,
        breaking_confidence_threshold=0.4,
        story_council_service=council,
        enable_story_council=True,
        council_max_candidates_per_cycle=3,
        max_story_age_for_posting_hours=max_story_age_for_posting_hours,
    )


@pytest.mark.asyncio
async def test_council_rejection_tries_next_candidate_immediately():
    story1 = _approved_story("Story One")
    story2 = _approved_story("Story Two")
    gating = FakeGatingService(allowed=True)
    council = FakeCouncilService(
        {"Story One": FakeVerdict(approved=False), "Story Two": FakeVerdict(approved=True)}
    )
    tweet_gen = FakeTweetGenerationService()
    posting = FakePostingService()
    rejection_repo = FakeRejectionRepository()

    orchestrator = _build_orchestrator([story1, story2], gating, council, tweet_gen, posting, rejection_repo)
    posted_count = await orchestrator.run_posting_window(max_stories=1)

    assert posted_count == 1
    assert council.reviewed_titles == ["Story One", "Story Two"]
    assert tweet_gen.generated_for == ["Story Two"]
    assert story1.status == StoryStatus.REJECTED
    assert story2.status == StoryStatus.POSTED
    assert len(rejection_repo.rejections) == 1


@pytest.mark.asyncio
async def test_gate_failure_stops_trying_further_candidates():
    story1 = _approved_story("Story One")
    story2 = _approved_story("Story Two")
    gating = FakeGatingService(allowed=False)
    council = FakeCouncilService({})
    tweet_gen = FakeTweetGenerationService()
    posting = FakePostingService()
    rejection_repo = FakeRejectionRepository()

    orchestrator = _build_orchestrator([story1, story2], gating, council, tweet_gen, posting, rejection_repo)
    posted_count = await orchestrator.run_posting_window(max_stories=1)

    assert posted_count == 0
    assert gating.calls == 1  # never even checked the second candidate


@pytest.mark.asyncio
async def test_stale_story_is_rejected_and_next_candidate_tried():
    story1 = _approved_story("Old Story")
    story2 = _approved_story("Fresh Story")
    gating = FakeGatingService(allowed=True)
    council = FakeCouncilService({"Fresh Story": FakeVerdict(approved=True)})
    tweet_gen = FakeTweetGenerationService()
    posting = FakePostingService()
    rejection_repo = FakeRejectionRepository()
    now = datetime.now(timezone.utc)
    articles_by_story = {
        story1.id: [Article(id=uuid4(), source_id=uuid4(), external_id="a1", title="t", url="u",
                             published_at=now - timedelta(hours=48))],
        story2.id: [Article(id=uuid4(), source_id=uuid4(), external_id="a2", title="t", url="u",
                             published_at=now - timedelta(hours=1))],
    }

    orchestrator = _build_orchestrator(
        [story1, story2], gating, council, tweet_gen, posting, rejection_repo,
        articles_by_story=articles_by_story,
    )
    posted_count = await orchestrator.run_posting_window(max_stories=1)

    assert posted_count == 1
    assert council.reviewed_titles == ["Fresh Story"]  # stale story never reached council
    assert story1.status == StoryStatus.REJECTED
    assert story2.status == StoryStatus.POSTED
    assert len(rejection_repo.rejections) == 1
