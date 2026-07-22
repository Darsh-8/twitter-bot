from datetime import datetime, timedelta, timezone

import pytest

from newsbot.application.services.gating_service import GatingService


class FakeTweetRepository:
    def __init__(self, count_today: int, last_posted_at: datetime | None):
        self._count_today = count_today
        self._last_posted_at = last_posted_at

    async def count_since(self, since: datetime) -> int:
        return self._count_today

    async def last_posted_at(self) -> datetime | None:
        return self._last_posted_at


@pytest.mark.asyncio
async def test_allows_post_when_under_cap_and_interval_elapsed():
    repo = FakeTweetRepository(count_today=2, last_posted_at=datetime.now(timezone.utc) - timedelta(hours=2))
    gate = GatingService(repo, max_tweets_per_day=8, min_post_interval_minutes=45, min_breaking_interval_minutes=10)
    decision = await gate.check(is_breaking=False)
    assert decision.allowed


@pytest.mark.asyncio
async def test_blocks_post_when_daily_cap_reached():
    repo = FakeTweetRepository(count_today=8, last_posted_at=None)
    gate = GatingService(repo, max_tweets_per_day=8, min_post_interval_minutes=45, min_breaking_interval_minutes=10)
    decision = await gate.check(is_breaking=False)
    assert not decision.allowed
    assert decision.reason == "daily_cap_reached"


@pytest.mark.asyncio
async def test_blocks_post_when_min_interval_not_met():
    repo = FakeTweetRepository(count_today=1, last_posted_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    gate = GatingService(repo, max_tweets_per_day=8, min_post_interval_minutes=45, min_breaking_interval_minutes=10)
    decision = await gate.check(is_breaking=False)
    assert not decision.allowed
    assert decision.reason == "min_interval_not_met"


@pytest.mark.asyncio
async def test_breaking_uses_relaxed_interval():
    repo = FakeTweetRepository(count_today=1, last_posted_at=datetime.now(timezone.utc) - timedelta(minutes=15))
    gate = GatingService(repo, max_tweets_per_day=8, min_post_interval_minutes=45, min_breaking_interval_minutes=10)
    decision = await gate.check(is_breaking=True)
    assert decision.allowed


@pytest.mark.asyncio
async def test_breaking_bypasses_daily_cap():
    repo = FakeTweetRepository(count_today=8, last_posted_at=datetime.now(timezone.utc) - timedelta(minutes=15))
    gate = GatingService(repo, max_tweets_per_day=8, min_post_interval_minutes=45, min_breaking_interval_minutes=10)
    decision = await gate.check(is_breaking=True)
    assert decision.allowed


@pytest.mark.asyncio
async def test_non_breaking_still_blocked_at_daily_cap_even_with_interval_elapsed():
    repo = FakeTweetRepository(count_today=8, last_posted_at=datetime.now(timezone.utc) - timedelta(hours=2))
    gate = GatingService(repo, max_tweets_per_day=8, min_post_interval_minutes=45, min_breaking_interval_minutes=10)
    decision = await gate.check(is_breaking=False)
    assert not decision.allowed
    assert decision.reason == "daily_cap_reached"


@pytest.mark.asyncio
async def test_breaking_still_blocked_by_its_own_interval_even_past_daily_cap():
    repo = FakeTweetRepository(count_today=8, last_posted_at=datetime.now(timezone.utc) - timedelta(minutes=2))
    gate = GatingService(repo, max_tweets_per_day=8, min_post_interval_minutes=45, min_breaking_interval_minutes=10)
    decision = await gate.check(is_breaking=True)
    assert not decision.allowed
    assert decision.reason == "min_interval_not_met"
